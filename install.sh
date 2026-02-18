#!/bin/bash

# Update package manager
echo "Updating package manager..."
sudo apt-get update && sudo apt-get upgrade -y

# Install dependencies (customize as needed)
echo "Installing dependencies..."
sudo apt-get install -y git build-essential

# Clone the repository
echo "Cloning the repository..."
git clone https://github.com/merian11936785951-creator/ayla.git
cd ayla

# Build or install (customize the following command as required)
echo "Running installation..."
# Example: If it's a Node.js project
# npm install
# If it's a Python project
# pip install -r requirements.txt

echo "Installation completed successfully!"

# Clean up (optional)
echo "Cleaning up..."
cd ..
rm -rf ayla

# End of script
