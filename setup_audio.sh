#!/bin/bash
# v0xHunt3r - Audio Setup Helper
# Verifies BlackHole installation and guides macOS audio configuration

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  v0xHunt3r - Audio Setup Checker"
echo "=========================================="
echo ""

# Check BlackHole 2ch
echo -n "Checking BlackHole 2ch... "
if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole 2ch"; then
    echo -e "${GREEN}INSTALLED${NC}"
    BH2=true
else
    echo -e "${RED}NOT FOUND${NC}"
    BH2=false
fi

# Check BlackHole 16ch
echo -n "Checking BlackHole 16ch... "
if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole 16ch"; then
    echo -e "${GREEN}INSTALLED${NC}"
    BH16=true
else
    echo -e "${RED}NOT FOUND${NC}"
    BH16=false
fi

echo ""

# Install if needed
if [ "$BH2" = false ] || [ "$BH16" = false ]; then
    echo -e "${YELLOW}Missing BlackHole drivers. Install with Homebrew:${NC}"
    echo ""
    if [ "$BH2" = false ]; then
        echo "  brew install blackhole-2ch"
    fi
    if [ "$BH16" = false ]; then
        echo "  brew install blackhole-16ch"
    fi
    echo ""
    read -p "Install now? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ "$BH2" = false ]; then
            echo "Installing BlackHole 2ch..."
            brew install blackhole-2ch
        fi
        if [ "$BH16" = false ]; then
            echo "Installing BlackHole 16ch..."
            brew install blackhole-16ch
        fi
        echo -e "${GREEN}Installation complete. You may need to restart your Mac.${NC}"
    else
        echo "Skipping installation."
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "  Manual Configuration Required"
echo "=========================================="
echo ""
echo -e "${YELLOW}Step 1: Create Multi-Output Device${NC}"
echo "  1. Open 'Audio MIDI Setup' (Spotlight: Audio MIDI Setup)"
echo "  2. Click '+' at bottom-left -> 'Create Multi-Output Device'"
echo "  3. Check BOTH:"
echo "     - Your speakers/headphones (for hearing audio)"
echo "     - BlackHole 2ch (for our tool to capture)"
echo "  4. Right-click the Multi-Output Device -> 'Use This Device For Sound Output'"
echo ""
echo -e "${YELLOW}Step 2: Set Browser Microphone${NC}"
echo "  1. In your browser, go to the AI interviewer page"
echo "  2. When asked for microphone permission, select 'BlackHole 16ch'"
echo "  3. This routes our TTS output as mic input to the browser"
echo ""
echo -e "${YELLOW}Step 3: Verify${NC}"
echo "  Run: python main.py --setup"
echo ""
echo -e "${GREEN}Audio routing diagram:${NC}"
echo ""
echo "  Browser Audio Out -> Multi-Output Device -> Speakers (you hear)"
echo "                                           -> BlackHole 2ch (tool captures)"
echo ""
echo "  Tool TTS -> BlackHole 16ch -> Browser Mic Input"
echo ""
