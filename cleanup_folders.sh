#!/bin/bash

# Check if directory path is provided as argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory_path>"
    exit 1
fi

# Store the directory path and max folders to keep
DIR_PATH="$1"
MAX_FOLDERS=7

# Set up logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/folder_cleanup.log"
MAX_LOG_SIZE_MB=10

# Check if directory exists
if [ ! -d "$DIR_PATH" ]; then
    echo "Error: Directory '$DIR_PATH' does not exist"
    exit 1
fi

# Function to write to log file
write_log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" | tee -a "$LOG_FILE"
    
    # Rotate log if it exceeds maximum size
    if [ -f "$LOG_FILE" ]; then
        local size=$(du -m "$LOG_FILE" | cut -f1)
        if [ "$size" -gt "$MAX_LOG_SIZE_MB" ]; then
            mv "$LOG_FILE" "$LOG_FILE.old"
            touch "$LOG_FILE"
            write_log "Log file rotated due to size limit"
        fi
    fi
}

# Function to clean excess folders
cleanup_excess_folders() {
    local target_dir="$1"
    
    write_log "Starting cleanup in directory: $target_dir"
    
    # Count total folders
    local folder_count=$(find "$target_dir" -mindepth 1 -maxdepth 1 -type d | wc -l)
    write_log "Current folder count: $folder_count"
    
    if [ "$folder_count" -le "$MAX_FOLDERS" ]; then
        write_log "No cleanup needed. Folder count ($folder_count) is within limit ($MAX_FOLDERS)"
        return
    fi
    
    # Calculate how many folders to remove
    local folders_to_remove=$((folder_count - MAX_FOLDERS))
    write_log "Need to remove $folders_to_remove folders"
    
    # Get list of folders sorted by modification time (oldest first)
    while IFS= read -r folder; do
        if [ -n "$folder" ] && [ "$folders_to_remove" -gt 0 ]; then
            rm -rf "$folder"
            write_log "Deleted folder: $folder"
            folders_to_remove=$((folders_to_remove - 1))
        fi
    done < <(find "$target_dir" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -n | cut -d' ' -f2-)
    
    # Log final folder count
    folder_count=$(find "$target_dir" -mindepth 1 -maxdepth 1 -type d | wc -l)
    write_log "Cleanup completed. Current folder count: $folder_count"
}

# Initialize log file
touch "$LOG_FILE"
write_log "=== Script Started ==="
write_log "Monitoring directory: $DIR_PATH"
write_log "Will maintain maximum of $MAX_FOLDERS folders"
write_log "Log file location: $LOG_FILE"

# Main loop
while true; do
    cleanup_excess_folders "$DIR_PATH"
    # Sleep for 1 hour before next check
    sleep 3600
done
