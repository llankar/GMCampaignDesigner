GMCampaignDesigner2
GMCampaignDesigner2 is an open-source campaign management tool designed to empower game masters to create, organize, and manage their tabletop campaigns. Built with Python and powered by customtkinter for a modern graphical interface, this project provides a modular framework for handling campaign components—such as factions, NPCs, places, and scenarios—in a flexible and extensible manner.

Overview
GMCampaignDesigner2 streamlines the creative process for game masters by consolidating essential planning and management tools into one application. The project is organized into clear, modular components that separate entity-specific logic from shared functionalities, making it easy to maintain and extend.

Key Features
Campaign Organization:

Manage campaigns by chapters, story arcs, or themes.
Organize and view detailed information for factions, NPCs, places, and scenarios.
Dynamic Data Management:

Load and save campaign data in JSON format.
Utilize a generic model wrapper for seamless CRUD (Create, Read, Update, Delete) operations on campaign elements.
Interactive User Interface:

Modern GUI built with customtkinter.
Centralized list view for displaying, searching, filtering, and sorting items.
Dedicated editor windows that dynamically adapt to each entity’s JSON template.
Rich Editing & Multimedia Support:

Advanced text fields supporting long descriptions with basic rich-text formatting.
Portrait support with automatic resizing and storage for NPCs and other entities.
Export Capabilities:

Export selected scenario details to a DOCX file, compiling associated information (like NPCs and places) for convenient sharing and documentation.
Developer-Friendly Design:

Modular architecture for easy expansion—new entities can be added with minimal effort.
Utility scripts for generating model wrappers and configuring the development environment (via VSCode).
(Project structure and functionality deduced from an analysis of the source files, including main_window.py, generic modules, and helper scripts.)

Project Structure
pgsql
Copier
GMCampaignDesigner2/
├── assets/                  # Image assets (e.g., portraits)
├── data/                    # JSON files for storing campaign data (factions, npcs, places, scenarios)
├── modules/
│   ├── factions/            # Faction-specific logic and editor window
│   ├── npcs/                # NPC-specific logic and editor window
│   ├── places/              # Place-specific logic and editor window
│   ├── scenarios/           # Scenario-specific logic and editor window
│   └── generic/             # Generic UI components and wrappers
│       ├── generic_list_view.py    # List view for displaying items
│       ├── generic_model_wrapper.py  # Wrapper for loading/saving JSON data
│       └── generic_editor_window.py  # Dynamic editor for items
├── main_window.py           # Main application window and entry point
├── generate_wrappers.py     # Script to auto-generate entity wrapper files
└── vscode_install.py        # Script to configure VSCode (creates virtual environment and settings)
Installation
Prerequisites
Python 3.8+ – Ensure Python is installed on your system.
Dependencies – Required packages are installed via the setup script or manually.
Quick Start
Clone the Repository:

bash
Copier
git clone https://github.com/llankar/GMCampaignDesigner2.git
cd GMCampaignDesigner2
Set Up Your Development Environment (Optional):
Use the provided VSCode setup script to create configuration files, a virtual environment, and install dependencies:

bash
Copier
python vscode_install.py
Run the Application:

bash
Copier
python main_window.py
This will launch the main window where you can manage factions, places, NPCs, and scenarios, as well as export scenario data.

Usage
Managing Entities:
From the main window, click on the corresponding button to open a management interface for factions, places, NPCs, or scenarios. Each interface features:

Add: Create new entries.
Edit: Modify existing entries via a dynamic editor window.
Delete: Remove entries.
Search & Filter: Quickly locate items using the built-in search functionality.
Exporting Scenarios:
The export functionality lets you select one or more scenarios and generate a DOCX file. This file compiles the scenario details along with related data (such as linked NPCs and places) for convenient offline viewing or sharing.

Contributing
Contributions to GMCampaignDesigner2 are welcome! To contribute:

Fork the Repository.
Create a Feature Branch:
bash
Copier
git checkout -b feature/your-feature-name
Commit Your Changes: Ensure your code follows the project’s coding style and is well-documented.
Open a Pull Request: Provide a detailed description of your changes and any relevant information.
Note: For major changes or new features, please open an issue first to discuss your ideas.

License
GMCampaignDesigner2 is licensed under the GPL-3.0 License. See the LICENSE file for further details.

Acknowledgements
Special thanks to the contributors and open-source community who help improve and maintain GMCampaignDesigner2. Your support makes continuous innovation possible!