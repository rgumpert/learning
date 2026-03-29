#!/bin/bash
FOLDER=~/Desktop/$(date +%Y-%m-%d)
mkdir $FOLDER
touch $FOLDER/notes.txt
echo "Created $FOLDER"

