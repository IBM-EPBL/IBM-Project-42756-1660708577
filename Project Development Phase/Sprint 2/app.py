from flask import Flask,render_template, request

app = Flask(__name__)
app.secret_key="hiii"

@app.route("/")
def index():
	return render_template("index.html")
	
@app.route("/login")                                      
def home():
	return render_template(login.html")

@app.route("/Registration")                                      
def form():
	return render_template("Registration.html")