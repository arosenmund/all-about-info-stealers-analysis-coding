# Module 6 Instructions

## Setup

1. In the lab environment, open the "Part 2.2 - Windows AWorkstation (RDP)" connection.
> It takes a moment to log you in and setup the desktop.

2. On the desktop, click powershellv7, and wait for the prompt.
> You may have to hit enter a few times.

3. Clone down the repository for the workshop.
```
git clone https://github.com/arosenmund/all-about-info-stealers-analysis-coding.git
```

4. Change directory into the repository Module 6 folder, and further into the test-windows-script folder.
```
cd all-about-info-stealers-analysis-coding\06-ai-enhanced-infostealer\test-windows\script

```

5. Run the powershell script.
```
.\Deploy-CredentialArtifacts.ps1

```

> You will see the successfull checks and deployment locations!

6. Now change to the windows classifier binary folder.

```
cd 06-ai-enhanced-infostealer\classifier-cli-scanner-poc-001-windows-x86_64

```

7s. Now, run the rust based classifier!!!
```
.\classifier-cli.exe scan --root 'C:\Users\' --model '.\artifacts\cnn\cnn-fp32-033.onnx' --manifest '.\artifacts\cnn\cnn-fp32-003.manifest.json' --show-paths'

```

> If it fails to run, check the paths and make sure you can "tab complete".

Now it will find tons of files that are candidates to match strings at the byte level that look like authentication.

Now open VSCode to follow along opening the Git Repo folder.

