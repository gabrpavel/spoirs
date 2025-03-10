import socket
import sys
import signal
import os
import time

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 1024

class Client:
    def __init__(self):
        self.client_socket = None
        self.running = True

    def signal_handler(self, sig, frame):
        print("\n[!] Закрытие клиента...")
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                pass
        sys.exit(0)

    def read_line(self):
        buffer = []
        while True:
            chunk = self.client_socket.recv(1)
            if not chunk:
                return ''
            buffer.append(chunk)
            if chunk == b'\n':
                break
        return b''.join(buffer).decode().strip()

    def start(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((HOST, PORT))
            print(f"[+] Подключено к серверу {HOST}:{PORT}")

            self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Включаем Keep-Alive

            while self.running:
                try:
                    command = input("Введите команду (ECHO/TIME/UPLOAD/DOWNLOAD/CLOSE): ").strip()
                    if not command:
                        continue

                    self.client_socket.sendall((command + "\n").encode())

                    if command.upper().startswith("UPLOAD"):
                        self.handle_upload(command)
                    elif command.upper().startswith("DOWNLOAD"):
                        self.handle_download(command)
                    else:
                        self.handle_regular_command(command)

                except (BrokenPipeError, ConnectionResetError):
                    print("[-] Соединение с сервером разорвано")
                    self.running = False
                    break
                except Exception as e:
                    print(f"[-] Ошибка: {str(e)}")
                    self.running = False
                    break

        except ConnectionRefusedError:
            print("[-] Не удалось подключиться к серверу.")
        finally:
            if self.client_socket:
                self.client_socket.close()

    def handle_upload(self, command):
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            print("Ошибка: укажите имя файла.")
            return

        filename = parts[1]
        try:
            response = self.read_line()
            if response != "READY":
                print(f"Ошибка: {response}")
                return

            file_size = os.path.getsize(filename)
            # Отправляем размер файла
            self.client_socket.sendall(f"{file_size}\n".encode())

            # Отправляем файл блоками
            with open(filename, "rb") as f:
                remaining = file_size
                start_time = time.time()
                while remaining > 0:
                    chunk = f.read(min(BUFFER_SIZE, remaining))
                    if not chunk:
                        break
                    self.client_socket.sendall(chunk)
                    remaining -= len(chunk)

            response = self.read_line()
            end_time = time.time()
            elapsed_time = end_time - start_time
            bitrate = (file_size / elapsed_time) / 1024  # битрейт в КБ/с
            print(f"[Сервер]: {response}. Скорость передачи: {bitrate:.2f} KB/s")
        except FileNotFoundError:
            print("Файл не найден.")
        except Exception as e:
            print(f"[-] Ошибка: {str(e)}")
            self.running = False

    def handle_download(self, command):
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            print("Ошибка: укажите имя файла.")
            return

        filename = parts[1]
        try:
            response = self.read_line()
            if response.startswith("READY"):
                parts = response.split()
                if len(parts) < 2:
                    print("Ошибка: сервер не указал размер файла.")
                    return
                try:
                    file_size = int(parts[1])
                except ValueError:
                    print("Ошибка: неверный размер файла.")
                    return

                received = 0
                with open(filename, "wb") as f:
                    start_time = time.time()
                    while received < file_size:
                        remaining = file_size - received
                        chunk = self.client_socket.recv(min(BUFFER_SIZE, remaining))
                        if not chunk:
                            print("[-] Соединение прервано.")
                            break
                        f.write(chunk)
                        received += len(chunk)
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    bitrate = (file_size / elapsed_time) / 1024  # битрейт в КБ/с
                    print(f"[Сервер]: Файл получен. Скорость передачи: {bitrate:.2f} KB/s")
            else:
                print(f"Ошибка: {response}")
        except Exception as e:
            print(f"[-] Ошибка: {str(e)}")
            self.running = False

    def handle_regular_command(self, command):
        try:
            response = self.read_line()
            print(f"[Сервер]: {response}")
            if command.upper() in ("CLOSE", "EXIT", "QUIT"):
                self.running = False
        except (ConnectionResetError, BrokenPipeError):
            print("[-] Соединение с сервером разорвано")
            self.running = False
        except Exception as e:
            print(f"[-] Ошибка при получении ответа: {str(e)}")
            self.running = False

if __name__ == "__main__":
    client = Client()
    client.start()
