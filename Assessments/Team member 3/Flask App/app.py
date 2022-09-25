from flask import Flask,render_template

app=Flask(__name__)

@app.route('/home')
def home():
    return render_template("homepage.html")
@app.route('/about')
def about():
    return render_template("about.html")
@app.route('/signin')
def signin():
    return render_template("signin.html")
app.run(debug=True)
