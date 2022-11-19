from turtle import st
from flask import Flask, render_template, request, redirect, jsonify, make_response, session, url_for,flash
import sqlite3 as sql
from markupsafe import escape
import ibm_db
#import db

conn=ibm_db.connect("DATABASE=bludb;HOSTNAME=21fecfd8-47b7-4937-840d-d791d0218660.bs2io90l08kqb1od8lcg.databases.appdomain.cloud;PORT=31864;SECURITY=SSL;SSLServerCertificate=DigiCertGlobalRootCA.crt;UID=ygy89638;PWD=Uh6RkVwd4GiMab4B","","")

app = Flask(__name__)
app.secret_key = 'HIII'

@app.route('/')
def index():
   return render_template('index.html')

@app.route('/signin')
def signin():
   return render_template('signin.html')

@app.route('/signup')
def retail():
   return render_template('signup.html')

@app.route('/form')
def about():
   return render_template('form.html')

@app.route('/card')
def signup():
   return render_template('card.html')

@app.route('/items')
def fruits():
   return render_template('items.html')

@app.route('/go to signup')
def go():
   return render_template('signup.html')

@app.route('/back')
def back():
   return render_template('signin.html')

@app.route('/data',methods = ['POST', 'GET'])
def data():
   if request.method == 'POST':
         
         name = request.form['name']          
         email = request.form['email']
         password = request.form['password']

         sql = "SELECT * FROM login WHERE email=?"
         stmt = ibm_db.prepare(conn, sql)
         ibm_db.bind_param(stmt,1,email)
         ibm_db.execute(stmt)
         account = ibm_db.fetch_assoc(stmt)
         flash("You Have Already Account,Please Go To Login")


         if account:
           return redirect("signup")
           
         else:
          insert_sql = "INSERT INTO login VALUES (?,?,?)"
          prep_stmt = ibm_db.prepare(conn, insert_sql)
          ibm_db.bind_param(prep_stmt,1,name)
          ibm_db.bind_param(prep_stmt,2,email)
          ibm_db.bind_param(prep_stmt,3,password)
          ibm_db.execute(prep_stmt)
          flash("Register Successfully")

   return redirect("signup")
         
'''         con = sql.connect("login.db")
         cur=con.cursor()
         cur.execute("INSERT INTO login (name,email,password) VALUES (?,?,?)",(name,email,password))
         con.commit()
         flash("Register successfully","success")   
      except:
        flash("Error in insert operation")
      finally:
        return redirect("signup")
        con.close()'''

@app.route('/login',methods = [ 'GET', 'POST'])  
def login():
    if request.method == 'POST':
        name = request.form['email']
        password = request.form['password']

        sql = "SELECT * FROM login WHERE email = ? AND password = ?"
        stmt = ibm_db.prepare(conn, sql)

        ibm_db.bind_param(stmt,1,name)
        ibm_db.bind_param(stmt,2,password)
        ibm_db.execute(stmt)
        account = ibm_db.fetch_assoc(stmt)
        print(account)
        if account:
            session['email'] = name
            return render_template("/index.html")
        else:
            flash("Invalid Username or Password")
    return render_template("/signin.html")



'''      con = sql.connect("login.db")
      con.row_factory = sql.Row
      cur = con.cursor()
      cur.execute("SELECT * from login where email=? and password=?",(name,password))
      data = cur.fetchone()
      if data:
         session["mail"] = data["email"]
         session["password"] = data["password"]
         return redirect("retail")
      else:
         flash("Username and Password Mismatch","danger")
   return redirect("/") ''' 

@app.route('/logout')
def logout():
   session.clear()
   return render_template('signin.html')


if __name__ == '__main__':
   app.run(debug = True)
