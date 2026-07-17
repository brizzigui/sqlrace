#!/bin/bash

# Exit on error
set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}        SQL Race Judge - Linux Starter Script       ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Check Docker & Compose
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# 2. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.${NC}"
    exit 1
fi

# 3. Start PostgreSQL Containers
echo -e "\n${GREEN}[1/5] Spinning up main and sandbox PostgreSQL databases...${NC}"
if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

echo -e "${YELLOW}Waiting 6 seconds for PostgreSQL services to initialize...${NC}"
sleep 6

# 4. Configure Python Virtual Environment
echo -e "\n${GREEN}[2/5] Creating Python virtual environment (venv)...${NC}"
python3 -m venv venv
source venv/bin/activate

# 5. Install Dependencies
echo -e "\n${GREEN}[3/5] Installing package requirements...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 6. Setup Databases and Seed admin
echo -e "\n${GREEN}[4/5] Running database tables initializations...${NC}"
python init_db.py

# 7. Start the Flask App Server
echo -e "\n${GREEN}[5/5] Launching competitive arena server...${NC}"
echo -e "${CYAN}----------------------------------------------------${NC}"
echo -e "${GREEN}Server starting successfully!${NC}"
echo -e "${CYAN}Open http://localhost:5000 in your browser to access the Arena.${NC}"
echo -e "${CYAN}----------------------------------------------------${NC}"
python app.py
