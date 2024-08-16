# Movie Tracker Notion

**Movie Tracker Notion** is a Python-based console application designed to automatically populate a Notion template called "Movie Tracker" with movie information gathered from IMDb.

You can download the Notion template from here:  
[Movie Tracker Template](https://simone-mille.notion.site/Movie-Tracker-Template-881d7724f3244634834dc3c0f97f4213)

## How to Create the Installer (for Windows)

To create an installer for this application on Windows, follow these steps:

### Prerequisites

1. **NSIS (Nullsoft Scriptable Install System):**  
   Download and install NSIS from the official website:  
   [Download NSIS](https://nsis.sourceforge.io/Download)

2. **Python 3.9:**  
   Ensure you have Python 3.9 installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

3. **Pynsist:**  
   Install Pynsist, the tool required to create the installer, by running the following command in your terminal or command prompt:

   ```bash
   pip install pynsist
   ```

### Creating the Installer

1. Navigate to the project's root directory where the `installer.cfg` file is located.

2. Run the following command to generate the installer:

   ```bash
   pynsist installer.cfg
   ```

   This command will create an executable that can be used to install the application on Windows.
