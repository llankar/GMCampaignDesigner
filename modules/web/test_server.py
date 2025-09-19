from flask import Flask
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello, world!"
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=31000, debug=True)
