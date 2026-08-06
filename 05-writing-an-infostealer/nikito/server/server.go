package main

import (
	_ "embed"
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
)

//go:embed static/index.html
var indexHTML []byte

type Info struct {
	CredType       string   `json:"credType"`
	Content        string   `json:"content"`
	FileContaining []string `json:"fileContaining"`
	Count          int      `json:"count"`
}

const maxHistory = 10_000

var (
	upgrader = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
	mu       sync.Mutex
	history  []Info
	clients  = map[*websocket.Conn]bool{}
)

func broadcast(f Info) {
	data, _ := json.Marshal(f)
	mu.Lock()
	defer mu.Unlock()
	for conn := range clients {
		if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
			conn.Close()
			delete(clients, conn)
		}
	}
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("ws upgrade:", err)
		return
	}

	mu.Lock()
	clients[conn] = true
	snapshot := make([]Info, len(history))
	copy(snapshot, history)
	mu.Unlock()

	for _, f := range snapshot {
		if err := conn.WriteJSON(f); err != nil {
			break
		}
	}

	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			mu.Lock()
			delete(clients, conn)
			mu.Unlock()
			return
		}
	}
}

func ingestHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	var batch []Info
	if err := json.NewDecoder(r.Body).Decode(&batch); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	mu.Lock()
	history = append(history, batch...)
	if len(history) > maxHistory {
		history = history[len(history)-maxHistory:]
	}
	mu.Unlock()
	for _, f := range batch {
		broadcast(f)
	}
	w.WriteHeader(http.StatusNoContent)
}

func main() {
	addr := flag.String("addr", ":8080", "listen address")
	flag.Parse()

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Write(indexHTML)
	})
	http.HandleFunc("/ws", wsHandler)
	http.HandleFunc("/ingest", ingestHandler)

	log.Println("Listening on http://localhost" + *addr)
	log.Fatal(http.ListenAndServe(*addr, nil))
}
