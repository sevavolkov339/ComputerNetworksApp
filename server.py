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
        buffer = b""
        try:
            while True:
                data = client_socket.recv(8192)
                if not data:
                    break
                    
                buffer += data
                while True:
                    try:
                        # Ищем начало JSON объекта
                        start = buffer.find(b'{')
                        if start == -1:
                            buffer = b""
                            break
                        buffer = buffer[start:]
                        
                        # Пробуем декодировать JSON
                        try:
                            message = json.loads(buffer.decode())
                            self.process_message(client_socket, message)
                            buffer = b""
                            break
                        except json.JSONDecodeError:
                            # Если JSON неполный, ждем следующую порцию данных
                            break
                            
                    except Exception as e:
                        logging.error(f"Error processing message: {str(e)}")
                        buffer = b""
                        break
                
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
        
        logging.info(f"Login attempt for user: {username}")
        
        try:
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            
            if result and bcrypt.checkpw(password.encode(), result[1]):
                self.clients[client_socket] = username
                response = {
                    'status': 'success',
                    'message': 'Login successful',
                    'action': 'login',
                    'username': username
                }
                logging.info(f"Login successful for user: {username}")
            else:
                response = {
                    'status': 'error',
                    'message': 'Invalid credentials',
                    'action': 'login'
                }
                logging.warning(f"Login failed for user: {username}")
                
            # Отправляем ответ
            response_data = json.dumps(response, ensure_ascii=False).encode()
            # Отправляем размер данных
            size_data = len(response_data).to_bytes(4, byteorder='big')
            client_socket.send(size_data)
            # Отправляем данные
            client_socket.send(response_data)
            logging.info(f"Sent login response to {username}")
            
        except Exception as e:
            logging.error(f"Error during login: {str(e)}")
            response = {
                'status': 'error',
                'message': str(e),
                'action': 'login'
            }
            response_data = json.dumps(response, ensure_ascii=False).encode()
            size_data = len(response_data).to_bytes(4, byteorder='big')
            client_socket.send(size_data)
            client_socket.send(response_data)
        finally:
            conn.close()
        
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
        
        logging.info(f"Received file transfer request from {sender} to {receiver}, file: {file_name}")
        
        if not all([sender, receiver, file_data, file_name]):
            logging.error("Missing required file transfer data")
            response = {
                'action': 'file',
                'status': 'error',
                'message': 'Missing required file transfer data'
            }
            response_data = json.dumps(response, ensure_ascii=False).encode()
            size_data = len(response_data).to_bytes(4, byteorder='big')
            client_socket.send(size_data)
            client_socket.send(response_data)
            return
            
        try:
            # Create files directory if it doesn't exist
            if not os.path.exists('files'):
                os.makedirs('files')
                
            # Декодируем file_data из base64
            try:
                file_bytes = base64.b64decode(file_data)
                logging.info(f"Successfully decoded file data for {file_name}")
            except Exception as e:
                logging.error(f"Error decoding file data: {str(e)}")
                response = {
                    'action': 'file',
                    'status': 'error',
                    'message': f'Error decoding file data: {str(e)}'
                }
                response_data = json.dumps(response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                return
            
            # Save file with normalized path
            timestamp = datetime.now().timestamp()
            safe_filename = f"{timestamp}_{file_name}"
            file_path = os.path.join('files', safe_filename)
            # Нормализуем путь для хранения и передачи
            file_path = os.path.normpath(file_path)
            file_path_for_clients = file_path.replace('\\', '/')
            
            try:
                with open(file_path, 'wb') as f:
                    f.write(file_bytes)
                logging.info(f"File saved successfully at {file_path}")
            except Exception as e:
                logging.error(f"Error saving file: {str(e)}")
                response = {
                    'action': 'file',
                    'status': 'error',
                    'message': f'Error saving file: {str(e)}'
                }
                response_data = json.dumps(response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                return
                
            # Store file reference in database
            conn = sqlite3.connect('chat.db')
            cursor = conn.cursor()
            
            try:
                cursor.execute('SELECT id FROM users WHERE username = ?', (sender,))
                sender_id = cursor.fetchone()[0]
                cursor.execute('SELECT id FROM users WHERE username = ?', (receiver,))
                receiver_id = cursor.fetchone()[0]
                
                # Сохраняем путь с прямыми слэшами в БД
                cursor.execute('''
                    INSERT INTO messages (sender_id, receiver_id, file_path, content)
                    VALUES (?, ?, ?, ?)
                ''', (sender_id, receiver_id, file_path_for_clients, f"[File: {file_name}]"))
                conn.commit()
                logging.info(f"File reference stored in database for {file_name}")
            except Exception as e:
                logging.error(f"Error storing file in database: {str(e)}")
                response = {
                    'action': 'file',
                    'status': 'error',
                    'message': f'Error storing file in database: {str(e)}'
                }
                response_data = json.dumps(response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                return
            
            # Forward file to receiver if online
            for client, username in self.clients.items():
                if username == receiver:
                    try:
                        forward_message = {
                            'action': 'message',
                            'sender': sender,
                            'content': f"[File: {file_name}]",
                            'is_file': True,
                            'file_path': file_path_for_clients, # Отправляем путь с прямыми слэшами
                            'timestamp': datetime.now().isoformat()
                        }
                        # Отправляем размер данных
                        json_data = json.dumps(forward_message, ensure_ascii=False).encode()
                        size_data = len(json_data).to_bytes(4, byteorder='big')
                        client.send(size_data)
                        client.send(json_data)
                        logging.info(f"File forwarded to {receiver}")
                    except Exception as e:
                        logging.error(f"Error forwarding file: {str(e)}")
                    break
                    
            # Отправляем подтверждение отправителю
            try:
                confirmation = {
                    'action': 'file',
                    'status': 'success',
                    'file_name': file_name,
                    'file_path': file_path_for_clients, # Отправляем путь с прямыми слэшами
                    'timestamp': datetime.now().isoformat()
                }
                response_data = json.dumps(confirmation, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                logging.info(f"Sent confirmation to sender {sender}")
            except Exception as e:
                logging.error(f"Error sending confirmation: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error handling file transfer: {str(e)}")
            try:
                error_response = {
                    'action': 'file',
                    'status': 'error',
                    'message': str(e)
                }
                response_data = json.dumps(error_response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
            except:
                pass
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
                    response_data = json.dumps(response, ensure_ascii=False).encode()
                    size_data = len(response_data).to_bytes(4, byteorder='big')
                    client_socket.send(size_data)
                    client_socket.send(response_data)
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
                    response_data = json.dumps(response, ensure_ascii=False).encode()
                    size_data = len(response_data).to_bytes(4, byteorder='big')
                    client_socket.send(size_data)
                    client_socket.send(response_data)
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
                response_data = json.dumps(response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                
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
                response_data = json.dumps(response, ensure_ascii=False).encode()
                size_data = len(response_data).to_bytes(4, byteorder='big')
                client_socket.send(size_data)
                client_socket.send(response_data)
                return
                
        except Exception as e:
            response = {'status': 'error', 'message': str(e), 'action': action or 'contacts'}
            response_data = json.dumps(response, ensure_ascii=False).encode()
            size_data = len(response_data).to_bytes(4, byteorder='big')
            client_socket.send(size_data)
            client_socket.send(response_data)
        finally:
            conn.close()

if __name__ == '__main__':
    server = ChatServer()
    server.start() 