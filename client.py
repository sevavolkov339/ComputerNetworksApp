import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import socket
import json
import threading
import os
from PIL import Image, ImageTk
import base64
import tkinter.font as tkFont
import ctypes
import sys
import subprocess
import shutil
from datetime import datetime

def load_font(font_path):
    if os.name == "nt":
        FR_PRIVATE  = 0x10
        FR_NOT_ENUM = 0x20
        path = os.path.abspath(font_path)
        ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)

class ChatClient:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.connected = False
        self.file_links = []
        self.setup_gui()
        
    def setup_gui(self):
        """Initialize the GUI"""
        self.root = tk.Tk()
        self.root.title("Chat Application")
        self.root.geometry("1920x1080")
        self.root.resizable(False, False)  # Запрещаем изменение размера окна
        self.root.configure(bg="#18191c")
        
        # Загружаем кастомный шрифт Jersey 10
        font_path = os.path.join(os.path.dirname(__file__), "Jersey10-Regular.ttf")
        load_font(font_path)
        try:
            self.pixel_font = tkFont.Font(family="Jersey 10", size=16)
        except Exception as e:
            messagebox.showwarning("Font Warning", f"Не удалось загрузить шрифт Jersey 10: {str(e)}\nИспользуется Courier.")
            self.pixel_font = tkFont.Font(family="Courier", size=16)
        
        # Configure styles with sharp edges and larger buttons
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#18191c')
        style.configure('TLabel', background='#18191c', foreground='#fff', font=self.pixel_font)
        style.configure('TButton', font=self.pixel_font, relief='flat', borderwidth=0, padding=18, background='#fff', foreground='#18191c')
        style.map('TButton', background=[('active', '#eaeaea')], foreground=[('active', '#18191c')])
        style.configure('TLabelFrame', background='#18191c', foreground='#00ff99', font=self.pixel_font)
        style.configure('TEntry', font=self.pixel_font, relief='flat', borderwidth=1, padding=10, fieldbackground='#fff', foreground='#18191c')
        
        # Header (светлая шапка)
        self.header = tk.Frame(self.root, bg="#f5f6fa", height=60)
        self.header.pack(side=tk.TOP, fill=tk.X)
        self.header_label = tk.Label(self.header, text="Chat Application", bg="#f5f6fa", fg="#18191c", font=self.pixel_font)
        self.header_label.pack(side=tk.LEFT, padx=30, pady=10)
        # Основной контейнер для содержимого
        self.main_frame = tk.Frame(self.root, bg="#18191c")
        self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Login frame
        self.login_frame = ttk.Frame(self.main_frame, padding="32")
        self.login_frame.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(self.login_frame, text="Username:", background="#18191c").grid(row=0, column=0, sticky=tk.W, pady=16)
        self.username_entry = ttk.Entry(self.login_frame, font=self.pixel_font, width=32)
        self.username_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=16)
        ttk.Label(self.login_frame, text="Password:", background="#18191c").grid(row=1, column=0, sticky=tk.W, pady=16)
        self.password_entry = ttk.Entry(self.login_frame, show="*", font=self.pixel_font, width=32)
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=16)
        button_frame = ttk.Frame(self.login_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=28)
        ttk.Button(button_frame, text="Login", command=self.login, width=20).pack(side=tk.LEFT, padx=16)
        ttk.Button(button_frame, text="Register", command=self.register, width=20).pack(side=tk.LEFT, padx=16)
        # Main chat frame (initially hidden)
        self.chat_frame = ttk.Frame(self.main_frame, padding="32")
        
        # Contacts list
        self.contacts_frame = tk.Frame(self.chat_frame, bg="#fff", bd=0, highlightthickness=0)
        self.contacts_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W), padx=(0, 24), pady=0)
        contacts_label = tk.Label(self.contacts_frame, text="Contacts", bg="#fff", fg="#18191c", font=self.pixel_font)
        contacts_label.pack(side=tk.TOP, anchor="w", padx=8, pady=(8, 0))
        self.contacts_listbox = tk.Listbox(self.contacts_frame, width=25, font=self.pixel_font, bg="#fff", fg="#18191c", relief='flat', borderwidth=0, highlightthickness=2, highlightbackground="#000", selectbackground="#eaeaea", selectforeground="#18191c")
        self.contacts_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        self.contacts_listbox.bind('<<ListboxSelect>>', self.on_contact_select)
        self.add_contact_btn = tk.Button(self.contacts_frame, text="Add Contact", command=self.add_contact, font=self.pixel_font, bg="#fff", fg="#18191c", bd=0, highlightthickness=2, highlightbackground="#000", activebackground="#eaeaea", activeforeground="#18191c")
        self.add_contact_btn.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(0, 16))
        
        # Chat area (canvas + скроллинг)
        self.chat_canvas_frame = tk.Frame(self.chat_frame, bg="#18191c")
        self.chat_canvas_frame.grid(row=0, column=1, sticky=(tk.N, tk.S, tk.E, tk.W), padx=0)
        
        self.chat_canvas = tk.Canvas(self.chat_canvas_frame, width=1400, height=800, bg="#18191c", highlightthickness=0)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar = tk.Scrollbar(self.chat_canvas_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.chat_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.chat_canvas.bind_all("<Button-5>", self._on_mousewheel)
        self.chat_canvas.bind('<Configure>', lambda e: self.chat_canvas.config(scrollregion=self.chat_canvas.bbox("all")))
        
        # Message input
        self.message_frame = ttk.Frame(self.chat_frame)
        self.message_frame.grid(row=1, column=1, sticky=(tk.W, tk.E))
        
        self.message_entry = ttk.Entry(self.message_frame, font=self.pixel_font, width=60)
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=12, pady=18)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        
        self.send_btn = tk.Button(self.message_frame, text="Send", font=self.pixel_font, bg="#fff", fg="#18191c", bd=0, highlightthickness=2, highlightbackground="#000", activebackground="#eaeaea", width=10, height=1, command=self.squash_and_stretch_send)
        self.send_btn.grid(row=0, column=1, padx=12)
        self.send_file_btn = tk.Button(self.message_frame, text="Send File", font=self.pixel_font, bg="#fff", fg="#18191c", bd=0, highlightthickness=2, highlightbackground="#000", activebackground="#eaeaea", activeforeground="#18191c", width=12, height=1, command=self.send_file)
        self.send_file_btn.grid(row=0, column=2, padx=12)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.chat_frame.columnconfigure(1, weight=1)
        self.chat_frame.rowconfigure(0, weight=1)
        self.message_frame.columnconfigure(0, weight=1)
        
    def connect(self):
        """Connect to the server"""
        try:
            self.socket.connect((self.host, self.port))
            self.connected = True
            # Start receiving thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return False
            
    def login(self):
        """Handle login"""
        if not self.connected and not self.connect():
            return
            
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
            
        message = {
            'action': 'login',
            'username': username,
            'password': password
        }
        
        try:
            print(f"Sending login request for user: {username}")
            # Отправляем данные
            json_data = json.dumps(message, ensure_ascii=False).encode()
            # Отправляем размер данных
            size_data = len(json_data).to_bytes(4, byteorder='big')
            self.socket.send(size_data)
            # Отправляем данные
            self.socket.send(json_data)
        except Exception as e:
            print(f"Error sending login request: {str(e)}")
            messagebox.showerror("Error", f"Failed to send login request: {str(e)}")
        
    def register(self):
        """Handle registration"""
        if not self.connected and not self.connect():
            return
            
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
            
        message = {
            'action': 'register',
            'username': username,
            'password': password
        }
        
        self.socket.send(json.dumps(message, ensure_ascii=False).encode())
        
    def add_contact(self):
        """Add a new contact"""
        contact = simpledialog.askstring("Add Contact", "Enter contact username:")
        if contact:
            message = {
                'action': 'contacts',
                'contact_action': 'add',
                'contact_username': contact
            }
            self.socket.send(json.dumps(message, ensure_ascii=False).encode())
            
    def display_history(self, messages):
        self.chat_canvas.delete("all")
        self.file_links = []
        y = 20
        for idx, msg in enumerate(messages):
            sender = msg.get('sender', '')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            file_path = msg.get('file_path')
            is_self = sender == self.username
            color = '#18191c'
            bubble_bg = '#fff'
            text_fg = '#18191c'
            x = 1400-40 if is_self else 40
            anchor = 'e' if is_self else 'w'
            box_width = 800
            
            # Формируем текст сообщения
            if file_path:
                file_name = os.path.basename(file_path)
                display_text = f"📎 [File: {file_name}]"
                # Сохраняем информацию о файле для обработки клика
                self.file_links.append({
                    'index': idx,
                    'file_path': file_path,
                    'x': x,
                    'y': y,
                    'w': box_width,
                    'h': 40
                })
            else:
                display_text = content if content is not None else ''
            
            # Рисуем облачко
            text_id = self.chat_canvas.create_text(
                x, y,
                text=f"{sender} ({timestamp}):\n{display_text}",
                anchor=anchor,
                font=self.pixel_font,
                fill=text_fg,
                width=box_width
            )
            
            bbox = self.chat_canvas.bbox(text_id)
            if bbox:
                self.chat_canvas.create_rectangle(
                    bbox[0]-16, bbox[1]-8,
                    bbox[2]+16, bbox[3]+8,
                    fill=bubble_bg,
                    outline="#eaeaea",
                    width=2
                )
                self.chat_canvas.tag_lower("current")
                self.chat_canvas.tag_raise(text_id)
                
                if file_path:
                    # Привязываем обработчик клика к тексту
                    self.chat_canvas.tag_bind(
                        text_id,
                        '<Button-1>',
                        lambda e, path=file_path: self.handle_file_click(path)
                    )
            y += (bbox[3] - bbox[1] + 40) if bbox else 60
        self.chat_canvas.config(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def handle_file_click(self, file_path):
        """Handle click on file in chat"""
        try:
            # Явно заменяем обратные слэши на прямые перед нормализацией
            file_path = file_path.replace('\\', '/')
            # Нормализуем путь для текущей ОС
            file_path_local = os.path.normpath(file_path)
            
            # Извлекаем имя файла из пути
            file_name = os.path.basename(file_path_local)
            
            # Проверяем существование файла
            if not os.path.exists(file_path_local):
                # Попробуем найти файл в папке files, если путь не абсолютный
                if not os.path.isabs(file_path_local):
                     alternative_path = os.path.join('files', file_name)
                     alternative_path = os.path.normpath(alternative_path)
                     if os.path.exists(alternative_path):
                         file_path_local = alternative_path
                     else:
                        messagebox.showerror("Error", f"File not found locally: {file_path_local}")
                        return
                else:
                    messagebox.showerror("Error", f"File not found locally: {file_path_local}")
                    return
            
            # Создаем диалог для выбора действия
            dialog = tk.Toplevel(self.root)
            dialog.title("File Action")
            dialog.geometry("300x150")
            dialog.transient(self.root)  # Делаем диалог модальным
            dialog.grab_set()  # Захватываем фокус
            
            # Центрируем диалог
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = (dialog.winfo_screenwidth() // 2) - (width // 2)
            y = (dialog.winfo_screenheight() // 2) - (height // 2)
            dialog.geometry(f'{width}x{height}+{x}+{y}')
            
            # Добавляем кнопки
            button_frame = tk.Frame(dialog)
            button_frame.pack(expand=True, fill='both', padx=20, pady=20)
            
            open_button = tk.Button(
                button_frame,
                text="Open",
                font=self.pixel_font,
                bg="#fff",
                fg="#18191c",
                bd=0,
                highlightthickness=2,
                highlightbackground="#000",
                activebackground="#eaeaea",
                width=10,
                height=1,
                command=lambda: [self.open_file(file_path_local), dialog.destroy()]
            )
            open_button.pack(side=tk.LEFT, padx=12)
            
            save_button = tk.Button(
                button_frame,
                text="Save As...",
                font=self.pixel_font,
                bg="#fff",
                fg="#18191c",
                bd=0,
                highlightthickness=2,
                highlightbackground="#000",
                activebackground="#eaeaea",
                width=12,
                height=1,
                command=lambda: [self.save_file(file_path_local), dialog.destroy()]
            )
            save_button.pack(side=tk.LEFT, padx=12)
            
            cancel_button = tk.Button(
                button_frame,
                text="Cancel",
                font=self.pixel_font,
                bg="#fff",
                fg="#18191c",
                bd=0,
                highlightthickness=2,
                highlightbackground="#000",
                activebackground="#eaeaea",
                width=10,
                height=1,
                command=dialog.destroy
            )
            cancel_button.pack(side=tk.LEFT, padx=12)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error handling file: {str(e)}")

    def open_file(self, file_path):
        """Open file"""
        try:
            # Нормализуем путь для текущей ОС
            file_path = os.path.normpath(file_path)
            
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', file_path], shell=True, check=True)
            else:  # linux
                subprocess.run(['xdg-open', file_path], check=True)
        except FileNotFoundError:
             messagebox.showerror("Error", f"Application to open file not found.")
        except subprocess.CalledProcessError as e:
             messagebox.showerror("Error", f"Failed to open file: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def save_file(self, file_path):
        """Save file"""
        try:
            # Нормализуем путь для текущей ОС
            file_path = os.path.normpath(file_path)
            
            # Получаем имя файла без пути
            file_name = os.path.basename(file_path)
            
            # Запрашиваем путь для сохранения
            save_path = filedialog.asksaveasfilename(
                initialfile=file_name,
                defaultextension=os.path.splitext(file_name)[1],
                filetypes=[("All Files", "*.*")]
            )
            
            if save_path:
                # Копируем файл
                shutil.copy2(file_path, save_path)
                messagebox.showinfo("Success", f"File saved to {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def handle_message(self, message):
        """Handle incoming messages"""
        print(f"Received message: {message}")
        
        # Обрабатываем ошибки сразу в основном потоке, т.к. это всплывающие окна
        if message.get('status') == 'error':
            error_msg = message.get('message', 'Unknown error')
            action = message.get('action', 'Unknown action')
            self.root.after(1, messagebox.showerror, "Error", f"{action.capitalize()} failed: {error_msg}")
            return
        
        if message.get('status') == 'success' and message.get('action') in ('login', 'register'):
            print("Login/Register successful, switching to chat interface")
            self.username = message.get('username', self.username_entry.get())
            self.login_frame.place_forget()
            self.chat_frame.place(relx=0.5, rely=0.5, anchor='center')
            # Загружаем контакты сразу после успешного входа
            self.root.after(1, self.load_contacts)
            return
        
        if message.get('action') == 'history':
            # Обновляем историю в основном потоке через after
            self.root.after(1, self.display_history, message.get('messages', []))
            return
        
        # Обрабатываем входящие сообщения и файлы
        if message.get('action') == 'message' or (message.get('action') == 'file' and message.get('is_file')):
            selected = self.contacts_listbox.curselection()
            if selected:
                contact = self.contacts_listbox.get(selected[0])
                sender = message.get('sender')
                receiver = message.get('receiver')
                # Если сообщение для текущего активного контакта (получатель или отправитель),
                # добавляем его напрямую в чат.
                if contact == sender or (contact == receiver and sender != self.username): # Added check to not double-add own sent messages
                    self.root.after(1, self.add_message_to_display, message)
                # If the message is for a different contact, we don't add it to the current chat display.
                # In a more complete application, you might add a notification/indicator for that contact.
            return

        # Обрабатываем только подтверждение об отправке файла (status=success, action=file)
        # Это сообщение приходит отправителю после успешной передачи файла на сервер и его сохранения.
        if message.get('action') == 'file' and message.get('status') == 'success':
             selected = self.contacts_listbox.curselection()
             if selected:
                 contact = self.contacts_listbox.get(selected[0])
                 # Если подтверждение для текущего активного контакта (отправителя),
                 # добавляем отправленный файл в чат отправителя.
                 # We already add the sent file in send_file's callback after a short delay,
                 # so we might not need to add it again here based on the server confirmation.
                 # Let's keep it for now but be mindful of potential duplicates.
                 if contact == message.get('receiver') and message.get('sender') == self.username:
                      self.root.after(1, messagebox.showinfo, "Success", "File sent successfully")
                     # self.root.after(1, self.add_message_to_display, message) # Removed to avoid potential duplicates

        elif message.get('action') == 'contacts':
            if message.get('status') == 'success':
                if 'contacts' in message:
                    self.contacts_listbox.delete(0, tk.END)
                    for contact in message['contacts']:
                        self.contacts_listbox.insert(tk.END, contact)
                    # Если есть контакты и ни один не выбран, выбираем первый и загружаем его историю
                    # Only load history if no contact is currently selected, to avoid clearing active chat
                    if message['contacts'] and not self.contacts_listbox.curselection():
                         self.root.after(1, lambda c=message['contacts'][0]: self.contacts_listbox.selection_set(0) or self.request_history(c))

            if message.get('message') == 'Contact added successfully':
                self.root.after(1, self.load_contacts)

        elif message.get('action') == 'history':
             # При получении полной истории, очищаем текущий чат и отображаем историю
             self.root.after(1, self.display_history, message.get('messages', []))

    def request_history(self, contact):
        """Request chat history with a contact"""
        print(f"Requesting history for contact: {contact}")
        message = {
            'action': 'contacts',
            'contact_action': 'history',
            'contact_username': contact
        }
        try:
            json_data = json.dumps(message, ensure_ascii=False).encode()
            size_data = len(json_data).to_bytes(4, byteorder='big')
            self.socket.send(size_data)
            self.socket.send(json_data)
        except Exception as e:
            print(f"Error requesting history: {str(e)}")
            messagebox.showerror("Error", f"Failed to load chat history: {str(e)}")

    def send_message(self):
        if not self.connected:
            return
        message = self.message_entry.get()
        if not message:
            return
        selected = self.contacts_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a contact")
            return
        receiver = self.contacts_listbox.get(selected[0])
        data = {
            'action': 'message',
            'receiver': receiver,
            'content': message
        }
        self.socket.send(json.dumps(data, ensure_ascii=False).encode())
        self.message_entry.delete(0, tk.END)
        # После отправки сообщения обновляем историю
        self.request_history(receiver)

    def send_file(self):
        if not self.connected:
            return
        selected = self.contacts_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a contact")
            return
        receiver = self.contacts_listbox.get(selected[0])
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
        try:
            # Get file size
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                messagebox.showerror("Error", "File size exceeds 10MB limit")
                return

            # Показываем индикатор загрузки
            self.send_file_btn.config(text="Uploading...", state='disabled')
            self.root.update()

            # Read file in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(file_path, 'rb') as f:
                file_data = b''
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    file_data += chunk

            # Encode file data
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            
            # Send file data
            data = {
                'action': 'file',
                'receiver': receiver,
                'file_name': os.path.basename(file_path),
                'file_data': encoded_data
            }
            
            try:
                # Отправляем данные
                json_data = json.dumps(data, ensure_ascii=False).encode()
                size_data = len(json_data).to_bytes(4, byteorder='big')
                self.socket.send(size_data)
                self.socket.send(json_data)
                
                # Сразу запрашиваем обновление истории у отправителя, не дожидаясь подтверждения
                self.root.after(100, self.request_history, receiver) # Небольшая задержка, чтобы сервер успел обработать
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send file: {str(e)}")
                if not self.connected:
                    self.connect()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send file: {str(e)}")
            if not self.connected:
                self.connect()
        finally:
            # Восстанавливаем кнопку в основном потоке через after
            self.root.after(100, lambda: self.send_file_btn.config(text="Send File", state='normal'))

    def receive_messages(self):
        """Receive messages from server"""
        buffer = b""
        # Define a fixed buffer size for initial reads, though the message size dictates total read
        # receive_buffer_size = 4096 # This was implicit before, making it explicit might help debugging
        while self.connected:
            try:
                # Ensure we have at least 4 bytes in the buffer to read the size
                while len(buffer) < 4:
                    packet = self.socket.recv(8192) # Read in chunks
                    if not packet:
                        print("Connection closed by server during size read")
                        self.connected = False
                        break
                    buffer += packet
                if not self.connected: break

                # Read the message size from the first 4 bytes of the buffer
                size = int.from_bytes(buffer[:4], byteorder='big')
                # Remove the size bytes from the buffer
                buffer = buffer[4:]

                # print(f"Received message size: {size}") # Keep this for debugging if needed

                if size > 1024 * 1024 * 10:  # Increased limit to 10MB for larger files, was 1MB
                    print(f"Invalid or excessively large message size: {size}. Discarding buffer.")
                    buffer = b"" # Discard buffer on excessively large size
                    continue # Go back to start of while self.connected loop

                # Ensure we have the complete message data in the buffer
                message_data = b""
                while len(message_data) < size:
                    # Read the remaining required bytes for the message
                    bytes_to_read = size - len(message_data)
                    packet = self.socket.recv(min(bytes_to_read, 8192)) # Read in chunks
                    if not packet:
                        print("Connection closed by server during message data read")
                        self.connected = False
                        break
                    message_data += packet
                if not self.connected: break # Check again if connection closed during data read

                # We now have exactly 'size' bytes for the message data
                try:
                    message = json.loads(message_data.decode())
                    # print(f"Processing message: {message}") # Keep for debugging
                    self.handle_message(message)
                    # Buffer is already updated by slicing after size read
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}. Discarding incomplete message.")
                    # On decode error, discard the current message data but keep the rest of the buffer
                    # buffer remains as is after slicing, ready for next potential message size header.
                except Exception as e:
                    print(f"Error processing message: {str(e)}")
                    # Similar to JSON decode error, keep remaining buffer

            except socket.error as e:
                print(f"Socket error: {str(e)}")
                self.connected = False
                # Attempt to reconnect only if the error wasn't due to clean disconnect
                # This part might need more sophisticated reconnection logic
                try:
                     print("Attempting to reconnect...")
                     self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                     self.socket.connect((self.host, self.port))
                     self.connected = True
                     print("Reconnection successful.")
                     # After successful reconnection, need to re-authenticate
                     # This is a limitation of current design - re-login is manual.
                     # A better approach would be to send login details automatically.
                except Exception as reconnect_e:
                     print(f"Reconnection failed: {str(reconnect_e)}")
                     break # Exit thread if reconnection fails
            except Exception as e:
                print(f"Error in receive_messages loop: {str(e)}")
                self.connected = False # Assume critical error, close connection

        # Clean up socket when thread exits
        try:
            self.socket.close()
            print("Socket closed.")
        except Exception as close_e:
            print(f"Error closing socket: {str(close_e)}")

    def load_contacts(self):
        """Load contact list"""
        print("Loading contacts...")
        message = {
            'action': 'contacts',
            'contact_action': 'list'
        }
        try:
            json_data = json.dumps(message, ensure_ascii=False).encode()
            size_data = len(json_data).to_bytes(4, byteorder='big')
            self.socket.send(size_data)
            self.socket.send(json_data)
        except Exception as e:
            print(f"Error loading contacts: {str(e)}")
            messagebox.showerror("Error", f"Failed to load contacts: {str(e)}")

    def on_contact_select(self, event):
        selected = self.contacts_listbox.curselection()
        if not selected:
            return
        contact = self.contacts_listbox.get(selected[0])
        self.request_history(contact)
        
    def _on_mousewheel(self, event):
        # Поддержка прокрутки для Windows и Mac
        if event.num == 5 or event.delta < 0:
            self.chat_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.chat_canvas.yview_scroll(-1, "units")

    def squash_and_stretch_send(self):
        # Анимация: меняем только цвет и текст, размер остается неизменным
        self.send_btn.config(bg="#eaeaea", text="Sending...")
        self.send_btn.after(100, lambda: self.send_btn.config(bg="#fff", text="Send"))
        self.send_message()

    def run(self):
        """Start the client"""
        self.root.mainloop()

    def update_chat_history(self, username, message, is_file=False, file_path=None):
        """Update chat history with new message"""
        # This method is no longer used for adding new messages directly to the display.
        # New messages for the active chat are now handled by add_message_to_display.
        # It might still be relevant if you implement a separate history view or logging.
        # Keeping it here for now, but its role has changed.
        pass # Or keep relevant logic if needed elsewhere

    def add_message_to_display(self, message):
        """Adds a single message to the chat display."""
        sender = message.get('sender', '')
        content = message.get('content', '')
        timestamp = message.get('timestamp', '')
        file_path = message.get('file_path')
        is_self = sender == self.username
        color = '#18191c' # Not directly used for text, but good to keep consistent
        bubble_bg = '#fff' if not is_self else '#00ff99' # Different background for sent messages
        text_fg = '#18191c'
        # Adjust x position and anchor based on sender
        x = self.chat_canvas.winfo_width() - 40 if is_self else 40
        anchor = 'e' if is_self else 'w'
        box_width = self.chat_canvas.winfo_width() - 80 # Adjust box width based on canvas size

        # Format the timestamp
        try:
            # Assuming timestamp is in ISO format from server
            dt_object = datetime.fromisoformat(timestamp)
            formatted_timestamp = dt_object.strftime("%H:%M")
        except ValueError:
            formatted_timestamp = timestamp # Use original if formatting fails

        # Формируем текст сообщения
        if file_path:
            file_name = os.path.basename(file_path)
            display_text = f"📎 [File: {file_name}]"
            # Note: File links are currently managed by display_history.
            # For real-time addition, we might need to adjust how file_links are stored and managed.
            # For now, the text with filename will be displayed. Clicking functionality might
            # still rely on a full history refresh or require more complex handling here.
        else:
            display_text = content if content is not None else ''

        # Рисуем облачко
        text_content = f"{sender} ({formatted_timestamp}):\n{display_text}"
        text_id = self.chat_canvas.create_text(
            x, self.chat_canvas.bbox("all")[3] + 20 if self.chat_canvas.find_all() else 20, # Position below the last item
            text=text_content,
            anchor=anchor,
            font=self.pixel_font,
            fill=text_fg,
            width=box_width
        )

        bbox = self.chat_canvas.bbox(text_id)
        if bbox:
            rect_id = self.chat_canvas.create_rectangle(
                bbox[0]-16, bbox[1]-8,
                bbox[2]+16, bbox[3]+8,
                fill=bubble_bg,
                outline="#eaeaea",
                width=2
            )
            self.chat_canvas.tag_lower(rect_id, text_id) # Draw rectangle behind text

            if file_path:
                 # Bind click handler to the text for files
                self.chat_canvas.tag_bind(
                    text_id,
                    '<Button-1>',
                    lambda e, path=file_path: self.handle_file_click(path)
                )


        # Update scroll region and scroll to the bottom
        self.chat_canvas.config(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

if __name__ == '__main__':
    client = ChatClient()
    client.run() 