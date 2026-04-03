# Gets the drive with the label "STUDIO20", searches for .mov files created on the latest Friday, Sunday, or Monday.
# For Sunday files, copies only the earliest video that is longer than 30 minutes.
# For Friday and Monday files, copies all videos longer than 30 minutes.
# It logs all actions to a filename.log.

$desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'))
$logFilePath = [System.IO.Path]::Combine("C:\Users\AudioVisual\Documents\GitHub\Video", "filename.log")

function Write-Log {
    param (
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$timestamp - $Message" | Out-File -FilePath $logFilePath -Append
}

# Get video length using ffprobe
function Get-VideoDuration {
    param (
        [string]$filePath
    )
    $ffprobePath = "ffprobe" # Ensure ffprobe is in your PATH
    $ffprobeArgs = @(
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        $filePath
    )
    try {
        $duration = & $ffprobePath $ffprobeArgs
        return [double]$duration
    } catch {
        Write-Log "Failed to get duration for '$filePath': $_"
        return $null
    }
}

# function Get-LatestDays {
#     # Get today's date
#     $today = Get-Date
    
#     # Calculate the last Friday
#     $daysSinceFriday = ($today.DayOfWeek - [int][System.DayOfWeek]::Friday + 7) % 7
#     $latestFriday = $today.AddDays(-$daysSinceFriday).Date

#     # Calculate the last Sunday
#     $daysSinceSunday = ($today.DayOfWeek - [int][System.DayOfWeek]::Sunday + 7) % 7
#     $latestSunday = $today.AddDays(-$daysSinceSunday).Date

#     # Calculate the last Monday
#     $daysSinceMonday = ($today.DayOfWeek - [int][System.DayOfWeek]::Monday + 7) % 7
#     $latestMonday = $today.AddDays(-$daysSinceMonday).Date

#     # Log the dates
#     Write-Log "Latest Friday: $latestFriday"
#     Write-Log "Latest Sunday: $latestSunday"
#     Write-Log "Latest Monday: $latestMonday"

#     return @($latestFriday, $latestSunday, $latestMonday)
# }

#The recorder won't accept dates past 2024, so going back to 2014
function Get-LatestDays {
    # Get today's date and calculate the offset year
    $today = Get-Date
    $yearOffset = $today.Year - 2026 
    $targetYear = 2015 + $yearOffset
    
    $todayOffset = Get-Date -Year $targetYear -Month $today.Month -Day $today.Day
    
    # Calculate the last Friday
    $daysSinceFriday = ($todayOffset.DayOfWeek - [int][System.DayOfWeek]::Friday + 7) % 7
    $latestFriday = $todayOffset.AddDays(-$daysSinceFriday).Date
    # Calculate the last Sunday
    $daysSinceSunday = ($todayOffset.DayOfWeek - [int][System.DayOfWeek]::Sunday + 7) % 7
    $latestSunday = $todayOffset.AddDays(-$daysSinceSunday).Date
    # Calculate the last Monday
    $daysSinceMonday = ($todayOffset.DayOfWeek - [int][System.DayOfWeek]::Monday + 7) % 7
    $latestMonday = $todayOffset.AddDays(-$daysSinceMonday).Date
    # Log the dates
    Write-Log "Latest Friday ($targetYear): $latestFriday"
    Write-Log "Latest Sunday ($targetYear): $latestSunday"
    Write-Log "Latest Monday ($targetYear): $latestMonday"
    return @($latestFriday, $latestSunday, $latestMonday)
}

# Find the drive with the volume label "STUDIO20"
$movDrive = Get-Volume | Where-Object { $_.FileSystemLabel -like "STUDIO20" }

if ($movDrive) {
    $driveLetter = $movDrive.DriveLetter
    Write-Log "Drive with label 'STUDIO20' found: ${driveLetter}:"

    # Source path
    $sourcePath = "${driveLetter}:\" 

    # Find all .mov files
    $movFiles = Get-ChildItem -Path $sourcePath -Filter *.mov -Recurse -ErrorAction SilentlyContinue

    if ($movFiles) {
        $datesToCheck = Get-LatestDays  # Get the latest Friday, Sunday, and Monday
        $latestFriday = $datesToCheck[0]
        $latestSunday = $datesToCheck[1]
        $latestMonday = $datesToCheck[2]
        
        # Create array just for Sunday files
        $sundayFiles = @()
        
        # First pass: Process files
        foreach ($file in $movFiles) {
            # Check if the file's creation date matches one of our target dates
            $fileDate = $file.CreationTime.Date
            
            # Skip if not on one of our target dates
            if ($datesToCheck -notcontains $fileDate) {
                Write-Log "File '$($file.FullName)' was not created on the latest Friday, Sunday, or Monday. Skipping."
                continue
            }
            
            # Get the length of the video file
            $duration = Get-VideoDuration -filePath $file.FullName
            if (-not $duration) {
                Write-Log "Could not determine the duration of '$($file.FullName)'. Skipping."
                continue
            }
            
            # Log the filename and its length
            Write-Log "File '$($file.Name)' duration: $([math]::Round($duration / 60, 2)) minutes."
            
            # Skip if shorter than 30 minutes
            if ($duration -le 1800) {
                Write-Log "File '$($file.FullName)' is shorter than 30 minutes. Skipping."
                continue
            }
            
            # Process based on day of week
            if ($fileDate -eq $latestSunday) {
                # For Sunday, add to the array for later processing
                $sundayFiles += $file
                Write-Log "File '$($file.FullName)' meets criteria for Sunday. Will select earliest later."
            }
            elseif ($fileDate -eq $latestFriday -or $fileDate -eq $latestMonday) {
                # Copy Friday and Monday files
                $destinationPath = [System.IO.Path]::Combine($desktopPath, $file.Name)
                Write-Log "Copying '$($file.FullName)' to '$destinationPath'"
                try {
                    Copy-Item -Path $file.FullName -Destination $destinationPath -Force
                    Write-Log "Successfully copied '$($file.FullName)' to '$destinationPath'"
                } catch {
                    Write-Log "Failed to copy '$($file.FullName)' to '$destinationPath': $_"
                }
            }
        }
        
        # Process Sunday files - copy only first service
        if ($sundayFiles.Count -gt 0) {
            if ($sundayFiles.Count -gt 1) {
                Write-Log "Found $($sundayFiles.Count) Sunday files. Selecting earliest."
                $earliestSundayFile = $sundayFiles | Sort-Object CreationTime | Select-Object -First 1
                Write-Log "Selected earliest file for Sunday: '$($earliestSundayFile.Name)' created at $($earliestSundayFile.CreationTime)"
            } else {
                Write-Log "Found only one Sunday file."
                $earliestSundayFile = $sundayFiles[0]
            }
            
            $destinationPath = [System.IO.Path]::Combine($desktopPath, $earliestSundayFile.Name)
            Write-Log "Copying '$($earliestSundayFile.FullName)' to '$destinationPath'"
            try {
                Copy-Item -Path $earliestSundayFile.FullName -Destination $destinationPath -Force
                Write-Log "Successfully copied '$($earliestSundayFile.FullName)' to '$destinationPath'"
            } catch {
                Write-Log "Failed to copy '$($earliestSundayFile.FullName)' to '$destinationPath': $_"
            }
        } else {
            Write-Log "No eligible files found for Sunday."
        }
        
        Write-Log "All .mov files have been processed."
    } else {
        Write-Log "No .mov files found on the drive."
    }
} else {
    Write-Log "No drive with label 'STUDIO20' found."
}