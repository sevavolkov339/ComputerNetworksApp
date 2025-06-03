# Chat Application

A real-time messaging application with file transfer capabilities, built using Python and socket programming.

## Features

- Real-time text messaging
- File transfer capabilities
- User authentication and registration
- Contact management
- Secure password storage using bcrypt
- SQLite database for data persistence

## System Architecture

The application follows a client-server architecture:

1. Server (`server.py`):
   - Handles client connections
   - Manages user authentication
   - Routes messages between clients
   - Stores messages and user data in SQLite database
   - Handles file transfers

2. Client (`client.py`):
   - Provides GUI interface using tkinter
   - Manages user sessions
   - Handles message sending and receiving
   - Manages contact list
   - Handles file transfers

## Protocol Specification

The application uses a custom JSON-based protocol for communication:

1. Authentication Messages:
```json
{
    "action": "login/register",
    "username": "string",
    "password": "string"
}
```

2. Text Messages:
```json
{
    "action": "message",
    "receiver": "string",
    "content": "string"
}
```

3. File Transfer:
```json
{
    "action": "file",
    "receiver": "string",
    "file_name": "string",
    "file_data": "base64_encoded_string"
}
```

4. Contact Management:
```json
{
    "action": "contacts",
    "contact_action": "add/list",
    "contact_username": "string"  // for add action only
}
```

## Setup Instructions

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python server.py
```

3. Start the client:
```bash
python client.py
```

## Usage

1. Register a new account or login with existing credentials
2. Add contacts using the "Add Contact" button
3. Select a contact from the list to start chatting
4. Use the message input field to send text messages
5. Use the "Send File" button to transfer files

## Security Features

- Passwords are hashed using bcrypt before storage
- File transfers are base64 encoded
- SQLite database for secure data storage
- Input validation and error handling

## Error Handling

The application includes comprehensive error handling for:
- Network connection issues
- Authentication failures
- File transfer errors
- Invalid user input
- Database operations

## Logging

The server maintains detailed logs in `server.log` for:
- User connections/disconnections
- Authentication attempts
- Message routing
- File transfers
- Error conditions 