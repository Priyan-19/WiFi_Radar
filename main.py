from web_server import WebServer

def main():
    print("="*40)
    print("      WiFi Radar Scanner Started      ")
    print("="*40)
    
    # Initialize and start the web server on port 80
    server = WebServer(port=80)
    
    try:
        # This will run the server loop indefinitely
        server.start()
    except KeyboardInterrupt:
        print("\nServer stopped manually.")

if __name__ == '__main__':
    main()
