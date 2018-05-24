import json

def my_handler(event, context):
    return 'hello world'

def wsgi_echo_handler(environ, start_response):
    path = environ['PATH_INFO']
    method = environ['REQUEST_METHOD']
    request_uri = environ['fc.request_uri']
    client_ip =environ['REMOTE_ADDR']
    query_string = environ.get('QUERY_STRING', '')
    ctx = environ["fc.context"]
    rfile = environ['wsgi.input']
    length = int(environ['CONTENT_LENGTH'])
    body = rfile.read(length)

    ret = {
        "path" : path,
        "method": method,
        "client_ip": client_ip,
        "request_uri": request_uri,
        "query_string": query_string,
        "body": str(body.decode()),
    }
    resp_headers_items = [("key1", "value1"), ("key2", "value2")]
    start_response('202 Accepted', resp_headers_items)
    return json.dumps(ret).encode()
