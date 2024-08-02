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
$command = "GetInputStatus";

// Set the URL for the request
$url = "http://$username:$password@$ip_address/Monarch/syncconnect/sdk.aspx?command=$command";

// Set up HTTP context options
$options = [
    "http" => [
        "header" => "Authorization: Basic " . base64_encode("$username:$password"),
        "ignore_errors" => true // To capture errors in the response
    ]
];

$context = stream_context_create($options);

// Perform the HTTP request
$response = @file_get_contents($url, false, $context);

// Handle errors and set response code before output
if ($response === FALSE) {
    http_response_code(500); // Set response code before output
    $error = error_get_last();
    echo json_encode(["status" => "Failed to connect", "error" => $error['message']]);
} else {
    $response = trim($response);
    echo json_encode(["status" => $response]);
}
?>