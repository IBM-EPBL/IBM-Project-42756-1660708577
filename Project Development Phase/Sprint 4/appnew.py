from flask import Flask, render_template, redirect, url_for, request, flash, escape, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField
from wtforms.validators import InputRequired, Length, Email, EqualTo
import openapi_client
from com.spoonacular import misc_api
import testmail
import ibm_db
import ibm_boto3
from ibm_botocore.client import Config, ClientError

import os
from dotenv import load_dotenv

load_dotenv()

DB_HOSTNAME = os.getenv("DB_HOSTNAME")
DB_PORT = os.getenv("DB_PORT")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASS")

COS_ENDPOINT = os.getenv("COS_ENDPOINT")
COS_API_KEY_ID = os.getenv("COS_API_KEY_ID")
COS_INSTANCE_CRN = os.getenv("COS_INSTANCE_CRN")

cos = ibm_boto3.resource("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

conn = ibm_db.connect(f"DATABASE=bludb;HOSTNAME={DB_HOSTNAME};PORT={DB_PORT};SECURITY=SSL;SSLServerCertificate=SSLCertificate.crt;UID={DB_USERNAME};PWD={DB_PASS}",'','')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECERT_KEY")

class LoginForm(FlaskForm):
    email = EmailField("email", validators=[InputRequired("Email is required"), Email()])
    password = PasswordField("password", validators=[InputRequired("Password is required")])

class RegisterForm(FlaskForm):
    username = StringField("username", validators=[InputRequired("Username is required")])
    email = EmailField("email", validators=[InputRequired("Email is required"), Email()])
    pass1 = PasswordField("pass1", validators=[InputRequired("Password is required"), EqualTo('pass2', message="Passwords must match"), Length(min=4, max=30, message="Length must be between 4 and 30")])
    pass2 = PasswordField("pass2")

class ForgetPassword(FlaskForm):
    email = EmailField("email", validators=[InputRequired("Email is required"), Email()])

@app.route("/")
def home():
    username = request.cookies.get('username')
    return render_template("home.html", username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if request.method=='POST' and form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        sql = f"SELECT * FROM USERS WHERE EMAIL='{escape(email)}'"
        stmt = ibm_db.exec_immediate(conn, sql)
        dic = ibm_db.fetch_both(stmt)
        if not dic or password != dic['PASSWORD']:
            flash("Incorrect email or password", "error")
            return redirect(url_for('login'))

        session['username'] =  dic['USERNAME']
        session['uid'] =  dic['UID']
        return redirect(url_for('dashboard'))
    else:
        return render_template("login.html", form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if request.method=='POST' and form.validate_on_submit():
        username = request.form['username']
        email = request.form['email']
        pass1 = request.form['pass1']
        sql = f"SELECT * FROM USERS WHERE EMAIL='{escape(email)}'"
        stmt = ibm_db.exec_immediate(conn, sql)
        dic = ibm_db.fetch_both(stmt)
        if dic:
            flash("User with the email already exist", "error")
            return redirect(url_for('login'))
        sql = "INSERT INTO USERS (USERNAME, EMAIL, PASSWORD) VALUES (?, ?, ?)"
        prep_stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(prep_stmt, 1, username)
        ibm_db.bind_param(prep_stmt, 2, email)
        ibm_db.bind_param(prep_stmt, 3, pass1)
        ibm_db.execute(prep_stmt)
        testmail.SendEmail(email, username)
        flash("Registration Successful", "success")
        response = redirect(url_for('login'))
        return response
    else:
        return render_template("SignUp.html", form=form)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    form = ForgetPassword()
    if request.method=='POST' and form.validate_on_submit():
        email = request.form['email']
        sql = f"SELECT * FROM USERS WHERE EMAIL='{escape(email)}'"
        stmt = ibm_db.exec_immediate(conn, sql)
        dic = ibm_db.fetch_both(stmt)
        if dic:
            flash("Email has been sent if user exist", "success")
            return redirect(url_for('forgot_password'))
        
        return render_template("forgot password.html", form=form)

    return render_template("Generate OTP.html", form=form)
    
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username')
    session.pop('uid')
    return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not 'username' in session:
        flash("Login to access pages", "error")
        return(redirect(url_for('home')))
    return render_template("card.html")

def get_item(bucket_name, item_name):
    print("Retrieving item from bucket: {0}, key: {1}".format(bucket_name, item_name))
    try:
        file = cos.Object(bucket_name, item_name).get()

        print("File Contents: {0}".format(file["Body"].read()))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to retrieve file contents: {0}".format(e))

def get_bucket_contents(bucket_name):
    print("Retrieving bucket contents from: {0}".format(bucket_name))
    try:
        files = cos.Bucket(bucket_name).objects.all()
        files_names = []
        for file in files:
            files_names.append(file.key)
            print("Item: {0} ({1} bytes).".format(file.key, file.size))
        return files_names
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to retrieve bucket contents: {0}".format(e))

def multi_part_upload(bucket_name, item_name, file_path):
    try:
        print("Starting file transfer for {0} to bucket: {1}\n".format(item_name, bucket_name))
        # set 5 MB chunks
        part_size = 1024 * 1024 * 5

        # set threadhold to 15 MB
        file_threshold = 1024 * 1024 * 15

        # set the transfer threshold and chunk size
        transfer_config = ibm_boto3.s3.transfer.TransferConfig(
            multipart_threshold=file_threshold,
            multipart_chunksize=part_size
        )

        # the upload_fileobj method will automatically execute a multi-part upload
        # in 5 MB chunks for all files over 15 MB
        with open(file_path, "rb") as file_data:
            cos.Object(bucket_name, item_name).upload_fileobj(
                Fileobj=file_data,
                Config=transfer_config
            )

        print("Transfer for {0} Complete!\n".format(item_name))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to complete multi-part upload: {0}".format(e))  
	
@app.route('/uploader', methods = ['GET', 'POST'])
def upload():
    if not 'username' in session:
        flash("Login to access pages", "error")
        return(redirect(url_for('home'))
)
    if request.method == 'POST':
        bucket=os.getenv("BUCKET_NAME")
        f = request.files['file']
        filename = f.filename
        file_path = os.path.join('static/uploads', filename)
        f.save(file_path)
        multi_part_upload(bucket,filename,file_path)
        uid = session['uid']
        sql = f"INSERT INTO imagedetails(img_link, uid) VALUES(?, ?)"
        imagelink = f"https://flask-app-test.s3.jp-tok.cloud-object-storage.appdomain.cloud/{escape(filename)}"
        prep_stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(prep_stmt, 1, imagelink)
        ibm_db.bind_param(prep_stmt, 2, uid)
        ibm_db.execute(prep_stmt)

        sql = f"SELECT ID FROM imagedetails WHERE img_link='{escape(imagelink)}'"
        stmt = ibm_db.exec_immediate(conn, sql)
        image_id = ibm_db.fetch_both(stmt)
        nutitionapi(imagelink,image_id)

        return redirect(url_for('pictures'))
       
    if request.method == 'GET':
        return render_template('foodservices.html')
    
def nutitionapi(imagelink,image_id):
    configuration = openapi_client.Configuration(
        host = "https://api.spoonacular.com"
    )
    configuration.api_key['apiKeyScheme'] = os.getenv("NUTRITION_API_KEY")

    with openapi_client.ApiClient(configuration) as api_client:
        api_instance = misc_api.MiscApi(api_client)
        image_url = imagelink
    try:
        api_response = api_instance.image_analysis_by_url(image_url)
        y = api_response
        cal= y["nutrition"]["calories"]["value"]
        Carb= y["nutrition"]["carbs"]["value"]
        fat= y["nutrition"]["fat"]["value"]
        protein= y["nutrition"]["protein"]["value"]
        name=y["category"]["name"]
        imageid=image_id["ID"]  
        sql = f"INSERT INTO nutritiondetails(calories,carbs,fat,protein,ref_id,name) VALUES('{escape(cal)}','{escape(Carb)}','{escape(fat)}','{escape(protein)}','{escape(imageid)}','{escape(name)}')"
        
        prep_stmt = ibm_db.prepare(conn, sql)

        ibm_db.execute(prep_stmt)
        flash("Successful db operation", "success")
        
    except openapi_client.ApiException as e:
        print("Exception when calling MiscApi->image_analysis_by_url: %s\n" % e) 

@app.route('/pictures', methods = ['GET', 'POST'])
def pictures():
    if not 'username' in session:
        flash("Login to access pages", "error")
        return(redirect(url_for('home')))
    uid = session['uid']
    sql = f"SELECT * FROM imagedetails where imagedetails.uid='{escape(uid)}'"
    stmt = ibm_db.exec_immediate(conn, sql)
    pic = ibm_db.fetch_both(stmt)
    pics=[]
    while pic != False:
        x=[pic["ID"], pic["IMG_LINK"]]   
        pics.append(x)
        pic = ibm_db.fetch_both(stmt)
    x = []
    for i in pics:
        sql = f"SELECT * FROM nutritiondetails,imagedetails where nutritiondetails.ref_id=imagedetails.id and nutritiondetails.ref_id  = {escape(i[0])}"
        print(i[0])
        stmt = ibm_db.exec_immediate(conn, sql)
        pic = ibm_db.fetch_both(stmt)
        x.append(pic)
    print(x)
    return render_template('storage.html', foods = x)

if __name__ == '__main__':
    app.run(debug=True)