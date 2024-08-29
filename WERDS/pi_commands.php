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

    $host = $_ENV['HOST'];
    $user = $_ENV['USER'];
    $keyLocation = $_ENV['KEYLOCATION'];

    $ssh = new SSH2($host);

    if ($ssh->login($user, RSA::load(file_get_contents($keyLocation)))) {
        $connectionStatus = "Connected";
        $command = escapeshellcmd($command);
        $output = $ssh->exec('./' . $command . '.sh 2>&1');
        $stdoutData = $output;
    } else {
        $connectionStatus = "Authentication failed";
    }

    return [
        'status' => $connectionStatus,
        'stdout' => $stdoutData,
        'stderr' => ""
    ];
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $command = $_POST['command'] ?? '';
    if ($command) {
        $result = send($command);
        header('Content-Type: application/json'); // Set content type to JSON
        echo json_encode($result);
    } else {
        header('Content-Type: application/json'); // Set content type to JSON
        echo json_encode(['status' => 'No command sent', 'stdout' => '', 'stderr' => '']);
    }
}
?>