Nextup Deployment Tool
A lightweight Linux desktop application for simplifying and automating the deployment of the Nextup Robotics system.

The tool provides a GUI where deployment staff can start, monitor, and stop predefined system/ROS2 commands without manually opening and managing multiple terminals.
Important: This application does not modify the existing robot software, ROS2 packages, launch files, or robot code. It only executes the deployment commands defined in its YAML configuration.

✨ Features
- 🖥️ GUI-based deployment
  - Start deployment from a single interface.
  - Monitor deployment status and logs.
- 💻 Visible terminal execution
  - Commands configured with terminal: true run inside visible terminal windows.
  - Operators can watch ROS2/system output in real time.
- ⚙️ YAML-based configuration
  - Add, edit, delete, and reorder deployment commands.
  - Change commands without modifying Python application code.
- ▶️ Sequential deployment
  - Commands can be executed in a predefined order.
  - Long-running commands can continue while the next deployment step starts.
- 🛑 Process control
  - Deployment-started processes can be tracked.
  - STOP is designed to terminate the deployment process tree rather than blindly killing unrelated existing robot services.
- 📝 Logging
  - Deployment status and command activity can be displayed and recorded.
- 🔧 Command Manager
  - Manage deployment steps directly from the application.
- 🌐 Web application support
  - Deployment steps can check/open an existing local web service.
- 🐧 Linux/Ubuntu focused
  - Designed for deployment PCs running Ubuntu/Linux.
🏗️ Architecture
┌───────────────────────────────┐
│     Nextup Deployment GUI     │
│           PySide6             │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       deployment.yaml         │
│  Commands / Order / Settings  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│      Deployment Engine        │
│   Process + Error Handling    │
└───────────────┬───────────────┘
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
   Terminal   ROS2      System
   Commands   Launches   Commands
       │        │         │
       └────────┼─────────┘
                ▼
        Existing Robot System
📁 Project Structure
nextup-deployment-tool/
│
├── app.py
├── deployment.yaml
├── requirements.txt
├── install.sh
├── run.sh
│
├── config/
├── logs/
├── assets/
└── .runtime/
Main files
File	Purpose
app.py	Main PySide6 application
deployment.yaml	Deployment commands and configuration
requirements.txt	Python dependencies
install.sh	Installation/setup script
run.sh	Application launcher
config/	Configuration files
logs/	Deployment logs
assets/	Application assets
.runtime/	Temporary runtime/process files


⚙️ Requirements
Recommended environment:
- Ubuntu/Linux
- Python 3
- python3-venv
- PySide6
- PyYAML
- A supported terminal emulator such as:
  - GNOME Terminal
  - XTerm
  - Konsole
  - XFCE Terminal
- Existing ROS2 installation if ROS2 commands are used
The tool does not install or replace ROS2.
🚀 Installation
Clone the repository:
git clone https://github.com/i-am-yashgarg/deploy-tool.git
cd deploy-tool
Make the scripts executable:
chmod +x install.sh run.sh
Run the installer:
./install.sh
Then launch the application:
./run.sh
If the project uses the Python virtual environment directly:
source .venv/bin/activate
python3 app.py
📝 Deployment Configuration
Deployment steps are defined in deployment.yaml.

Example:
steps:

  - id: step1
    name: Start EtherCAT
    command: "sudo /etc/init.d/ethercat start"
    working_directory: "~"
    terminal: true
    wait: true

  - id: step2
    name: Start Nextup MoveIt
    command: "source install/setup.bash && ros2 launch nextup_moveit_config everything.launch.py"
    working_directory: "~/NextupRobot"
    terminal: true
    wait: false

  - id: step3
    name: Open Nextup Web
    command: "curl -fsS http://localhost:3000 > /dev/null && xdg-open http://localhost:3000"
    working_directory: "~"
    terminal: true
    wait: true
Configuration fields
id
Unique identifier for the deployment step.
id: step1
name
Human-readable name displayed in the application.
name: Start EtherCAT
command
The command that will be executed.
command: "sudo /etc/init.d/ethercat start"
working_directory
Directory in which the command runs.
working_directory: "~/NextupRobot"
terminal
Controls whether the command runs in a visible terminal.
terminal: true
Use:
true  → visible terminal
false → background/captured execution
wait
Controls whether the deployment waits for the command to finish.
wait: true
For long-running ROS2 processes:
wait: false
This allows the deployment process to continue to the next step while the command keeps running.
🖥️ Visible Terminal Mode
When:
terminal: true
the application opens a terminal and runs the command inside it.

The operator can see:
Command
   ↓
Terminal
   ↓
Live output
   ↓
ROS2/system processes
This is especially useful for long-running robotics commands such as ROS2 launch processes.
🛑 STOP and Process Safety
The application tracks the processes started by the deployment tool.

Conceptually:
Deployment Tool
      │
      ▼
Terminal
      │
      ▼
Deployment Wrapper
      │
      ▼
ROS2 Command
      │
      ├── Child Process
      ├── Child Process
      └── Child Process
When STOP is pressed, the application attempts to stop the deployment process tree.

The goal is to avoid using broad commands such as:
killall ros2
or:
pkill -f move_group
because those could terminate unrelated services that were already running.
🔧 Command Manager
The application supports managing deployment steps through the GUI.

Typical operations include:
Add
Edit
Delete
Move Up
Move Down
Save
This allows deployment staff to change the deployment sequence without editing Python source code.
📊 Example Deployment Flow
START
  │
  ▼
Environment / Configuration
Check
  │
  ▼
Start EtherCAT
  │
  ▼
Start MoveIt
  │
  ├──────────────► MoveIt continues running
  │
  ▼
Open / Check Web Interface
  │
  ▼
Additional Deployment Steps
  │
  ▼
SUCCESS
🧪 Testing
Before using the tool on a production robot, test each deployment command individually.

Recommended testing sequence:
1. Verify the command manually.
2. Verify its working directory.
3. Add it to deployment.yaml.
4. Run the command through the application.
5. Confirm terminal output.
6. Confirm the process remains running when expected.
7. Test STOP.
8. Verify unrelated existing robot services remain running.
9. Test failure/error handling.
10. Perform a complete deployment sequence.
🌐 Demonstration Website
An interactive demonstration website is included separately as an index.html.

The website demonstrates:
- Deployment workflow
- Visible terminal concept
- Step-by-step execution
- YAML configuration
- Process management concept
- Application features
The website is intended for demonstration purposes only and does not execute real robot commands.
🔗 Source Code
GitHub repository:

https://github.com/i-am-yashgarg/deploy-tool.git
🎯 Purpose
The main purpose of the Nextup Deployment Tool is to replace a manual deployment workflow such as:
Open terminal
     ↓
Type command
     ↓
Open another terminal
     ↓
Type another command
     ↓
Monitor ROS2 processes
     ↓
Open web interface
     ↓
Repeat on every deployment
with:
Open Nextup Deployment Tool
          ↓
     START DEPLOYMENT
          ↓
Commands execute automatically
          ↓
Visible terminals show live output
          ↓
Deployment status is displayed
          ↓
SUCCESS
This makes the deployment process more repeatable, easier to operate, and less dependent on manually remembering terminal commands.
