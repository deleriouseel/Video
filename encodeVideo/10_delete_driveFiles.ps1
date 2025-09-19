# Deletes all files on the STUDIO20 drive that are older than the latest Friday (last week's).
# Updated to handle files with 2014 dates due to firmware issue.

$movDrive = Get-Volume | Where-Object { $_.FileSystemLabel -eq "STUDIO20" }
$logFilePath = [System.IO.Path]::Combine("C:\Users\AudioVisual\Documents\GitHub\Video", "filename.log")

function Write-Log {
    param (
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$timestamp - $Message" | Out-File -FilePath $logFilePath -Append
}

function Get-LatestFriday {
    $today = Get-Date
    $latestFriday = $today.AddDays(-((7 + $today.DayOfWeek - [System.DayOfWeek]::Friday) % 7))

    return $latestFriday.Date 
}

function Get-AdjustedFileDate {
    param (
        [System.IO.FileInfo]$File
    )
    
    # If the file's creation year is 2014, assume it's actually from the current year
    # but keep the same month and day
    if ($File.CreationTime.Year -eq 2014) {
        $currentYear = (Get-Date).Year
        $adjustedDate = Get-Date -Year $currentYear -Month $File.CreationTime.Month -Day $File.CreationTime.Day -Hour $File.CreationTime.Hour -Minute $File.CreationTime.Minute -Second $File.CreationTime.Second
        return $adjustedDate.Date
    } else {
        # For files not affected by the firmware issue, use the actual creation date
        return $File.CreationTime.Date
    }
}

if ($movDrive) {
    $driveLetter = $movDrive.DriveLetter
    Write-Log "Drive with label 'STUDIO20' found: ${driveLetter}:"

    # Source path
    $sourcePath = "${driveLetter}:\"  

    # Get the latest Friday
    $latestFriday = Get-LatestFriday  
    Write-Log "Latest Friday: $latestFriday"

    # Get all files on the drive
    $allFiles = Get-ChildItem -Path $sourcePath -Recurse -File -ErrorAction SilentlyContinue

    if ($allFiles) {
        foreach ($file in $allFiles) {
            
            # Get the adjusted file date (handling 2014 firmware issue)
            $adjustedFileDate = Get-AdjustedFileDate -File $file
            
            Write-Log "Checking file: '$($file.FullName)' with original creation date: $($file.CreationTime), adjusted date: $adjustedFileDate"

            # Compare adjusted date with latest Friday
            if ($adjustedFileDate -lt $latestFriday) {
                Write-Log "File '$($file.FullName)' (adjusted date: $adjustedFileDate) is older than the latest Friday. Deleting..."

                # Delete the file
                try {
                    Remove-Item -Path $file.FullName -Force
                    Write-Log "Successfully deleted '$($file.FullName)'"
                } catch {
                    Write-Log "Failed to delete '$($file.FullName)': $_"
                }
            } else {
                Write-Log "File '$($file.FullName)' with adjusted date '$adjustedFileDate' is newer than the latest Friday. Skipping."
            }
        }
        Write-Log "All files have been processed."
    } else {
        Write-Log "No files found on the drive."
    }
} else {
    Write-Log "No drive with label 'STUDIO20' found."
}