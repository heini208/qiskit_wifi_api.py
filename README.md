# OpenRoberta + Qiskit Setup

This guide describes how to set up **OpenRoberta Lab** (this fork/branch) together with the **Qiskit WiFi/TCP server**.

## Folder structure

Create your workspace so it looks like this:

```text
~/roberta/
├─ openroberta-lab/
├─ qiskit_wifi_api.py/
├─ ora-cc-rsc/
└─ cc/
   └─ gcc-arm-none-eabi-10.3-2021.10/
      └─ bin/
```

## Prerequisites

Follow the upstream OpenRoberta prerequisites first:
- https://github.com/OpenRoberta/openroberta-lab#:~:text=compilation%20of%20course.-,Prerequisites,-You%20need%20Java

If open-jdk-11 cannot be found try:
```bash
sudo nano /etc/apt/sources.list
```
Add this line at the bottom:
```bash

deb http://deb.debian.org/debian bullseye main
```
```bash

sudo apt update
sudo apt install openjdk-11-jdk

java -version
```

## Clone OpenRoberta Lab (this fork + branch)

```bash
cd ~/roberta
git clone https://github.com/heini208/openroberta-lab.git
cd openroberta-lab
git checkout feature/calliope_qiskit
```

## Install Calliope-CC prerequisites

```bash
sudo apt-get update
sudo apt-get install -y srecord libssl-dev
```

## Install GNU ARM toolchain

Download **GNU Arm Embedded Toolchain**:

- https://developer.arm.com/downloads/-/gnu-rm

Choose the correct archive for your system:

```bash
uname -m  # check whether you need aarch64 or x86_64
```

Extract it (example; adjust filename and destination):

```bash
mkdir -p ~/roberta/cc
tar -xvjf gcc-*.tar.bz2 -C ~/roberta/cc
```

Add the toolchain `bin` directory to your `PATH` (adjust the path to match your extracted folder):

```bash
echo 'export PATH="$PATH:/home/pi/roberta/cc/gcc-arm-none-eabi-10.3-2021.10/bin"' >> ~/.profile
source ~/.profile
```

Verify:

```bash
arm-none-eabi-g++ --version
# expected: 10.3.1 (or similar)
```

## Clone `ora-cc-rsc` resources

```bash
cd ~/roberta
git clone https://github.com/OpenRoberta/ora-cc-rsc.git
```

Export the cross-compiler resource base (adjust the path if needed):

```bash
echo 'export robot_crosscompiler_resourcebase="/home/pi/roberta/ora-cc-rsc"' >> ~/.bashrc
source ~/.bashrc
```

## Build OpenRoberta Lab

```bash
cd ~/roberta/openroberta-lab
mvn clean install -DskipTests
./admin.sh -git-mode create-empty-db
```

## Clone the Qiskit TCP server

```bash
cd ~/roberta
git clone https://github.com/heini208/qiskit_wifi_api.py.git
```

## Install Qiskit server requirements (Python venv)

```bash
sudo apt-get update
sudo apt-get install -y python3-full python3-venv

cd ~/roberta/qiskit_wifi_api.py
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the Qiskit TCP server

Start manually:

```bash
cd ~/roberta/qiskit_wifi_api.py
source .venv/bin/activate
python qiskit_wifi_api.py
```

> Optional: You can add a start script to autostart (systemd, cron @reboot, etc.).

## Start OpenRoberta Lab

```bash
cd ~/roberta/openroberta-lab
./ora.sh start-from-git
```
## Add to Autostart
```bash

mkdir -p ~/.config/autostart
nano ~/.config/autostart/roberta.desktop
```

Add this:
```bash

[Desktop Entry]
Type=Application
Name=Roberta Script
Exec=/home/pi/roberta/qiskit_wifi_api.py/start_roberta.sh
StartupNotify=false
Terminal=false
```
```bash

chmod +x /home/pi/roberta/qiskit_wifi_api.py/start_roberta.sh

sudo reboot
```

## One Time Network Configuration on the PI
If offline mode start local hotspot:
```bash
bash ~/roberta/qiskit_wifi_api.py/start_hotspot.sh
```
If Online Mode and previously hotspot used reenable wifi:
```bash
bash ~/roberta/qiskit_wifi_api.py/enable_wifi.sh
```
After changing network configuration restart the server:
restart pi
or: 
```bash
bash ~/roberta/qiskit_wifi_api.py/start_roberta.sh
```
## Ports / URLs

- **OpenRoberta Lab** runs on the IP shown by the Python server on port `1999` (HTTP): `http://<ip>:1999`
- **Qiskit TCP server** runs on the same IP on port `5000`: `http://<ip>:5000`
