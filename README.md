# OpenRoberta + Qiskit Setup

# Folder Structure
# Make sure you have this folder structure:
# ~/roberta/openroberta-lab
# ~/roberta/qiskit_wifi_api.py
# ~/roberta/ora-cc-rsc
# ~/roberta/cc/gcc-arm-none-eabi-10.3-2021.10/bin

# Install Prerequisites
# Follow instructions here:
# https://github.com/OpenRoberta/openroberta-lab#:~:text=compilation%20of%20course.-,Prerequisites,-You%20need%20Java

# Pull the Lab
git clone https://github.com/heini208/openroberta-lab.git
cd open-roberta-lab
git checkout feature/calliope_qiskit

# Download Calliope-CC
sudo apt-get install srecord libssl-dev

# Download GNU ARM Toolchain:
# https://developer.arm.com/downloads/-/gnu-rm
# Put xtensa next to roberta and add bin path to ~/.profile
uname -m  # check if you need aarch or x86_64
tar -xvjf gcc...
echo export PATH="$PATH:PATHTOBIN" >> ~/.profile
source ~/.profile
arm-none-eabi-g++ --version
# >> 10.3.1

# Clone ora-cc Resource
git clone https://github.com/OpenRoberta/ora-cc-rsc.git
echo export robot_crosscompiler_resourcebase="/home/pi/roberta/ora-cc-rsc" >> ~/.bashrc
source ~/.bashrc

# Build the Lab
cd ~/roberta/openroberta-lab
mvn clean install -DskipTests
./admin.sh -git-mode create-empty-db

# Pull Qiskit TCP Server
git clone https://github.com/heini208/qiskit_wifi_api.py.git

# Install Qiskit Requirements
sudo apt install -y python3-full python3-venv
cd ~/roberta/qiskit_wifi_api.py/

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# (Optional) Add start script to autostart
# Or start manually:
cd ~/roberta/qiskit_wifi_api.py/
source .venv/bin/activate
python qiskit_wifi_api.py

# Start OpenRoberta Lab
cd ~/roberta/openroberta-lab
./ora.sh start-from-git

# Lab is running on the IP shown by the Python server on port :1999
# Qiskit is on the same IP with port :5000