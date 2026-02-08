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


