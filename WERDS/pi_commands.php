<?php
require 'vendor/autoload.php'; // Make sure Composer's autoload is included

use phpseclib3\Net\SSH2;
use phpseclib3\Crypt\RSA;

$dotenv = Dotenv\Dotenv::createImmutable(__DIR__);
$dotenv->load();
function send($command)
{
    $connectionStatus = "Not connected";
    $stdoutData = "";
    $stderrData = "";

    // Load environment variables
    $host = $_ENV['HOST'];
    $user = $_ENV['USER'];
    $keyLocation = $_ENV['KEYLOCATION'];

    // Initialize SSH connection
    $ssh = new SSH2($host);

    if ($ssh->login($user, RSA::load(file_get_contents($keyLocation)))) {
        $connectionStatus = "Connected";

        // Execute command and capture both stdout and stderr
        $command = escapeshellcmd($command); // Sanitize the command
        $output = $ssh->exec('./' . $command . '.sh 2>&1'); // Redirect stderr to stdout
        $stdoutData = $output; // Output contains both stdout and stderr
    } else {
        $connectionStatus = "Authentication failed";
    }

    return [
        'status' => $connectionStatus,
        'stdout' => $stdoutData,
        'stderr' => "" // stderr is included in stdout due to redirection
    ];
}

// Example usage
// $result = send('chromium-check');
// echo "Status: " . $result['status'] . "\n";
// echo "Output: " . $result['stdout'] . "\n";
?>