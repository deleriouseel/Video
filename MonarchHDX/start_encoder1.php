<?php
require_once 'vendor/autoload.php';

use Dotenv\Dotenv;

error_reporting(E_ALL);
ini_set('display_errors', 1);

// Initialize Dotenv and load .env file
$dotenv = Dotenv::createImmutable(__DIR__);
$dotenv->load();

$username = $_ENV['NAME'];
$password = $_ENV['PASSWORD'];
$ip_address = $_ENV['IP_ADDRESS'];
$command = "StartEncoder1";

$url = "http://$username:$password@$ip_address/Monarch/syncconnect/sdk.aspx?command=$command";

$options = [
    "http" => [
        "header" => "Authorization: Basic " . base64_encode("$username:$password")
    ]
];

$context = stream_context_create($options);
$response = file_get_contents($url, false, $context);

if ($response === FALSE) {
    echo json_encode(["status" => "Failed to connect"]);
    http_response_code(500);
} else {
    $response = trim($response);
    echo json_encode(["status" => $response]);
}