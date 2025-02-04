# Deletes all .MOV and .mp4 files on the Desktop that are older than the latest Friday (last week's).


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

# Get the current user's Desktop path
$desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")

Write-Log "Checking Desktop path: $desktopPath"

if (Test-Path -Path $desktopPath) {
    # Get the latest Friday
    $latestFriday = Get-LatestFriday
    Write-Log "Latest Friday: $latestFriday"

    # Get all .MOV and .mp4 files on the Desktop
    $allFiles = Get-ChildItem -Path $desktopPath -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -eq ".mov" -or $_.Extension -eq ".mp4"
    }

    if ($allFiles) {
        foreach ($file in $allFiles) {
            Write-Log "File: '$($file.FullName)' created: $($file.CreationTime)"

            # Compare creation date with latest Friday
            if ($file.CreationTime.Date -lt $latestFriday) {

                try {
                    Remove-Item -Path $file.FullName -Force
                    Write-Log "Deleted '$($file.FullName)'"
                } catch {
                    Write-Log "Failed to delete '$($file.FullName)': $_"
                }
            } else {
                Write-Log "Skipped File '$($file.FullName)' created '$($file.CreationTime.Date)'."
            }
        }
        Write-Log "All files have been processed."
    } else {
        Write-Log "No .MOV or .mp4 files found on the Desktop."
    }
} else {
    Write-Log "Desktop path '$desktopPath' does not exist."
}