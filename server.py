import socket
import threading
import time
import os
import signal
import sys

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 1024

class Server:
    def __init__(self):
        self.server_running = True
        self.server_socket = None
        self.active_connections = []
        self.lock = threading.Lock()

    def handle_client(self, conn, addr):
        print(f"[+] Подключен клиент: {addr}")
        try:
            with conn:
                while self.server_running:
                    try:
                        data = conn.recv(BUFFER_SIZE).decode().strip()
                        if not data:
                            break

                        print(f"[>] Получено: {data}")

                        response = self.process_command(data, conn)
                        conn.sendall((response + "\n").encode())

                        if data.upper() in ("CLOSE", "EXIT", "QUIT"):
                            break
                    except (ConnectionResetError, BrokenPipeError):
                        break
        finally:
            with self.lock:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
            print(f"[-] Соединение с {addr} закрыто")

    def read_line(self, conn):
        buffer = []
        while True:
            chunk = conn.recv(1)
            if not chunk:
                return ''
            buffer.append(chunk)
            if chunk == b'\n':
                break
        return b''.join(buffer).decode().strip()

    def process_command(self, data, conn):
        try:
            if data.upper().startswith("ECHO"):
                return data[5:]
            elif data.upper() == "TIME":
                return time.ctime()
            elif data.upper().startswith("UPLOAD"):
                parts = data.split(maxsplit=1)
                if len(parts) < 2:
                    return "Ошибка: укажите имя файла."
                filename = parts[1]
                conn.sendall("READY\n".encode())

                # Получаем размер файла
                file_size_str = self.read_line(conn)
                if not file_size_str:
                    return "Ошибка: не получен размер файла."
                try:
                    file_size = int(file_size_str)
                except ValueError:
                    return "Ошибка: неверный размер файла."

                # Принимаем данные файла
                received = 0
                start_time = time.time()
                with open(filename, "wb") as f:
                    while received < file_size:
                        remaining = file_size - received
                        chunk = conn.recv(min(BUFFER_SIZE, remaining))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)

                end_time = time.time()
                elapsed_time = end_time - start_time
                if received == file_size:
                    bitrate = (file_size / elapsed_time) / 1024  # битрейт в КБ/с
                    return f"Файл {filename} загружен. Скорость передачи: {bitrate:.2f} KB/s"
                else:
                    return f"Ошибка: получено {received} из {file_size} байт."
            elif data.upper().startswith("DOWNLOAD"):
                parts = data.split(maxsplit=1)
                if len(parts) < 2:
                    return "Ошибка: укажите имя файла."
                filename = parts[1]
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    conn.sendall(f"READY {file_size}\n".encode())
                    with open(filename, "rb") as f:
                        remaining = file_size
                        start_time = time.time()
                        while remaining > 0:
                            chunk = f.read(min(BUFFER_SIZE, remaining))
                            conn.sendall(chunk)
                            remaining -= len(chunk)

                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    bitrate = (file_size / elapsed_time) / 1024  # битрейт в КБ/с
                    return f"Файл {filename} отправлен. Скорость передачи: {bitrate:.2f} KB/s"
                return "Файл не найден."
            elif data.upper() in ("CLOSE", "EXIT", "QUIT"):
                return "Соединение закрыто."
            return "Неизвестная команда"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    def signal_handler(self, sig, frame):
        print("\n[!] Завершение работы сервера...")
        self.server_running = False

        with self.lock:
            for conn in self.active_connections.copy():
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                except Exception as e:
                    pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                pass

        print("[!] Сервер остановлен.")
        sys.exit(0)

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Включаем Keep-Alive

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen()
            print(f"[+] Сервер запущен на {HOST}:{PORT}")

            while self.server_running:
                try:
                    conn, addr = self.server_socket.accept()
                    with self.lock:
                        self.active_connections.append(conn)
                    client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except OSError:
                    break
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = Server()
    server.start()
