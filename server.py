import socket
import threading
import json
import sqlite3
import os
import bcrypt
from datetime import datetime
import logging
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = {}  # {client_socket: username}
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect('chat.db')
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                contact_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (contact_id) REFERENCES users (id)
            )
        ''')
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                content TEXT,
                file_path TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def start(self):
        """Start the server and listen for connections"""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logging.info(f"Server started on {self.host}:{self.port}")
        
        while True:
            client_socket, address = self.server_socket.accept()
            logging.info(f"New connection from {address}")
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()
            
    def handle_client(self, client_socket):
        """Handle individual client connections"""
        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                message = json.loads(data.decode())
                self.process_message(client_socket, message)
                
        except Exception as e:
            logging.error(f"Error handling client: {str(e)}")
        finally:
            if client_socket in self.clients:
                del self.clients[client_socket]
            client_socket.close()
            
    def process_message(self, client_socket, message):
        """Process incoming messages from clients"""
        action = message.get('action')
        
        if action == 'register':
            self.handle_registration(client_socket, message)
        elif action == 'login':
            self.handle_login(client_socket, message)
        elif action == 'message':
            self.handle_message(client_socket, message)
        elif action == 'file':
            self.handle_file_transfer(client_socket, message)
        elif action == 'contacts':
            self.handle_contacts(client_socket, message)
            
    def handle_registration(self, client_socket, message):
        """Handle user registration"""
        username = message.get('username')
        password = message.get('password')
        
        try:
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, hashed_password))
            conn.commit()
            
            response = {'status': 'success', 'message': 'Registration successful', 'action': 'register'}
        except sqlite3.IntegrityError:
            response = {'status': 'error', 'message': 'Username already exists', 'action': 'register'}
        except Exception as e:
            response = {'status': 'error', 'message': str(e), 'action': 'register'}
        finally:
            conn.close()
            
        client_socket.send(json.dumps(response, ensure_ascii=False).encode())
        
    def handle_login(self, client_socket, message):
        """Handle user login"""
        username = message.get('username')
        password = message.get('password')
        
        try:
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            
            if result and bcrypt.checkpw(password.encode(), result[1]):
                self.clients[client_socket] = username
                response = {'status': 'success', 'message': 'Login successful', 'action': 'login'}
            else:
                response = {'status': 'error', 'message': 'Invalid credentials', 'action': 'login'}
        except Exception as e:
            response = {'status': 'error', 'message': str(e), 'action': 'login'}
        finally:
            conn.close()
            
        client_socket.send(json.dumps(response, ensure_ascii=False).encode())
        
    def handle_message(self, client_socket, message):
        """Handle text messages"""
        sender = self.clients.get(client_socket)
        receiver = message.get('receiver')
        content = message.get('content')
        
        if not all([sender, receiver, content]):
            return
            
        try:
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            # Get user IDs
            cursor.execute('SELECT id FROM users WHERE username = ?', (sender,))
            sender_id = cursor.fetchone()[0]
            cursor.execute('SELECT id FROM users WHERE username = ?', (receiver,))
            receiver_id = cursor.fetchone()[0]
            
            # Store message
            cursor.execute('''
                INSERT INTO messages (sender_id, receiver_id, content)
                VALUES (?, ?, ?)
            ''', (sender_id, receiver_id, content))
            conn.commit()
            
            # Forward message to receiver if online
            for client, username in self.clients.items():
                if username == receiver:
                    forward_message = {
                        'action': 'message',
                        'sender': sender,
                        'content': content,
                        'timestamp': datetime.now().isoformat(),
                        'receiver': receiver
                    }
                    client.send(json.dumps(forward_message, ensure_ascii=False).encode())
                    break
                    
        except Exception as e:
            logging.error(f"Error handling message: {str(e)}")
        finally:
            conn.close()
            
    def handle_file_transfer(self, client_socket, message):
        """Handle file transfers"""
        sender = self.clients.get(client_socket)
        receiver = message.get('receiver')
        file_data = message.get('file_data')
        file_name = message.get('file_name')
        
        if not all([sender, receiver, file_data, file_name]):
            return
            
        try:
            # Create files directory if it doesn't exist
            if not os.path.exists('files'):
                os.makedirs('files')
                
            # Декодируем file_data из base64
            file_bytes = base64.b64decode(file_data)
            
            # Save file
            file_path = os.path.join('files', f"{datetime.now().timestamp()}_{file_name}")
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
                
            # Store file reference in database
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM users WHERE username = ?', (sender,))
            sender_id = cursor.fetchone()[0]
            cursor.execute('SELECT id FROM users WHERE username = ?', (receiver,))
            receiver_id = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO messages (sender_id, receiver_id, file_path, content)
                VALUES (?, ?, ?, ?)
            ''', (sender_id, receiver_id, file_path, f"[File: {file_name}]"))
            conn.commit()
            
            # Forward file to receiver if online
            for client, username in self.clients.items():
                if username == receiver:
                    forward_message = {
                        'action': 'file',
                        'sender': sender,
                        'file_name': file_name,
                        'file_data': file_data,  # Отправляем оригинальные данные
                        'timestamp': datetime.now().isoformat(),
                        'receiver': receiver
                    }
                    client.send(json.dumps(forward_message, ensure_ascii=False).encode())
                    break
                    
            # Отправляем подтверждение отправителю
            confirmation = {
                'action': 'file',
                'status': 'success',
                'file_name': file_name,
                'timestamp': datetime.now().isoformat()
            }
            client_socket.send(json.dumps(confirmation, ensure_ascii=False).encode())
                    
        except Exception as e:
            logging.error(f"Error handling file transfer: {str(e)}")
            error_response = {
                'action': 'file',
                'status': 'error',
                'message': str(e)
            }
            client_socket.send(json.dumps(error_response, ensure_ascii=False).encode())
        finally:
            conn.close()
            
    def handle_contacts(self, client_socket, message):
        """Handle contact management"""
        username = self.clients.get(client_socket)
        action = message.get('contact_action')
        contact_username = message.get('contact_username')
        
        try:
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            if action == 'add':
                # Проверяем, существует ли контакт
                cursor.execute('SELECT id FROM users WHERE username = ?', (contact_username,))
                contact = cursor.fetchone()
                if not contact:
                    response = {'status': 'error', 'message': 'Contact user does not exist', 'action': 'contacts'}
                    client_socket.send(json.dumps(response, ensure_ascii=False).encode())
                else:
                    # Добавляем только если такой связи еще нет
                    cursor.execute('''
                        INSERT OR IGNORE INTO contacts (user_id, contact_id)
                        SELECT u1.id, u2.id
                        FROM users u1, users u2
                        WHERE u1.username = ? AND u2.username = ?
                    ''', (username, contact_username))
                    conn.commit()
                    # После добавления сразу отправляем обновленный список контактов
                    cursor.execute('''
                        SELECT u.username
                        FROM contacts c
                        JOIN users u ON c.contact_id = u.id
                        JOIN users u2 ON c.user_id = u2.id
                        WHERE u2.username = ?
                    ''', (username,))
                    contacts = [row[0] for row in cursor.fetchall()]
                    response = {'status': 'success', 'message': 'Contact added successfully', 'contacts': contacts, 'action': 'contacts'}
                    client_socket.send(json.dumps(response, ensure_ascii=False).encode())
                return
                
            elif action == 'list':
                cursor.execute('''
                    SELECT u.username
                    FROM contacts c
                    JOIN users u ON c.contact_id = u.id
                    JOIN users u2 ON c.user_id = u2.id
                    WHERE u2.username = ?
                ''', (username,))
                contacts = [row[0] for row in cursor.fetchall()]
                response = {'status': 'success', 'contacts': contacts, 'action': 'contacts'}
                client_socket.send(json.dumps(response, ensure_ascii=False).encode())
                
            elif action == 'history':
                # Получаем id пользователей
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                user_id = cursor.fetchone()[0]
                cursor.execute('SELECT id FROM users WHERE username = ?', (contact_username,))
                contact_id = cursor.fetchone()[0]
                # Получаем все сообщения между двумя пользователями
                cursor.execute('''
                    SELECT sender_id, content, file_path, sent_at
                    FROM messages
                    WHERE (sender_id = ? AND receiver_id = ?)
                       OR (sender_id = ? AND receiver_id = ?)
                    ORDER BY sent_at ASC
                ''', (user_id, contact_id, contact_id, user_id))
                messages = []
                for row in cursor.fetchall():
                    sender = username if row[0] == user_id else contact_username
                    messages.append({
                        'sender': sender,
                        'content': row[1],
                        'file_path': row[2],
                        'timestamp': row[3]
                    })
                response = {'status': 'success', 'action': 'history', 'messages': messages}
                client_socket.send(json.dumps(response, ensure_ascii=False).encode())
                return
                
        except Exception as e:
            response = {'status': 'error', 'message': str(e), 'action': action or 'contacts'}
            client_socket.send(json.dumps(response, ensure_ascii=False).encode())
        finally:
            conn.close()

if __name__ == '__main__':
    server = ChatServer()
    server.start() 