## LOC Metrics Data Model

The LOCMetrics schema is used to represent lines-of-code metrics at project, package, or file granularity. Below are the fields:

| Field         | Type    | Description                                                      |
|-------------- |---------|------------------------------------------------------------------|
| repo_id       | string  | Unique identifier for the repository                             |
| repo_name     | string  | Repository name                                                  |
| branch        | string  | Branch name                                                      |
| commit_hash   | string  | Commit hash                                                      |
| language      | string  | Programming language                                             |
| granularity   | string  | Granularity: 'project', 'package', or 'file'                     |
| project_name  | string? | Project name if applicable                                       |
| package_name  | string? | Package name if applicable                                       |
| file_path     | string? | File path if applicable                                          |
| total_loc     | int     | Total lines of code                                              |
| code_loc      | int     | Lines of code (excluding comments and blanks)                    |
| comment_loc   | int     | Lines of comments                                                |
| blank_loc     | int     | Blank lines                                                      |
| collected_at  | string  | Timestamp when metrics were collected (ISO format)               |

Example (file granularity):

```
{
   "repo_id": "123",
   "repo_name": "example-repo",
   "branch": "main",
   "commit_hash": "abc123",
   "language": "Python",
   "granularity": "file",
   "file_path": "src/main.py",
   "total_loc": 1000,
   "code_loc": 800,
   "comment_loc": 150,
   "blank_loc": 50,
   "collected_at": "2026-02-12T12:00:00Z"
}
```
Prerequisites
Make sure the following are installed on your system:
1. Git
   Used to clone the repository.
   
Check if installed:

git --version

If not installed:

Mac (Homebrew):

brew install git

Windows:

Download from: https://git-scm.com/download/win

Linux:

sudo apt install git

2. Docker Desktop (includes Docker Compose)
   
Required to build and run containers.

Check if installed:

docker --version

docker compose version

If not installed:

Mac:
https://docs.docker.com/desktop/install/mac-install/

Windows:
https://docs.docker.com/desktop/install/windows-install/

Linux:
https://docs.docker.com/desktop/install/linux-install/

After installation, make sure Docker Desktop is running.

Clone the Repository

git clone https://github.com/kperam1/RepoPulse.git

cd RepoPulse

Build the Project

docker compose build

Run the Project

docker compose up

Access the API

Open in browser:

http://localhost:8080/

Or test using curl:

curl http://localhost:8080/

Stop the Project

docker compose down


