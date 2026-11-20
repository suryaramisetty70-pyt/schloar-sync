import argparse
import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3000)
    parser.add_argument('--strictPort', action='store_true')
    args = parser.parse_args()
    uvicorn.run('scholarsync.app:app', host=args.host, port=args.port)
