#!/bin/bash
# Activate the virtual environment (adjust the path if necessary)
source /var/services/homes/llankar/Drive/rpg/Python/GMCampaignDesigner2/venvDS/bin/activate

# Change to the project root directory
cd /var/services/homes/llankar/Drive/rpg/Python/GMCampaignDesigner2

# Run the Flask app using the module command.
# (Make sure you run from the project root so Python locates your packages.)
python -m modules.web.GM_webviewer
