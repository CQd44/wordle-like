#wordle-like
#technically works!
#port 42069

import psycopg2
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import toml

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static") #logo and favicon go here

CONFIG = toml.load("./config.toml") # load variables from toml file
CONNECT_STR = f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}'

TEST_WORD = "QUEUE" #5 letter word, all caps. This is the word the users are trying to guess.
HINT = "Where calls wait!" #the hint you can show to users to guide them towards the correct answer

WORDS = []
ROW_1 = "QWERTYUIOP"
ROW_2 = "ASDFGHJKL"
ROW_3 = "ZXCVBNM"
ALPHA_COLORS_1 = {letter: "white" for letter in ROW_1}
ALPHA_COLORS_2 = {letter: "white" for letter in ROW_2}
ALPHA_COLORS_3 = {letter: "white" for letter in ROW_3}

with open('WORDS.txt', 'r') as file: # loads up dictionary of good 5 letter words. prevents users from spamming guesses with gibberish. 
    lines = file.readlines()
    for line in lines:
        WORDS.append(line.strip())

@app.on_event("startup")
async def startup_event():
    try:
        init_db()
    except Exception as e:
        print(e)

@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request) -> HTMLResponse:
    user_ip = request.client.host # type: ignore
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    
    html_content = """
<!DOCTYPE html>
<html>
<head><meta charset = "UTF-8">
<style>
table {
    margin-bottom: 10px;
    margin-top: 10px;
}

.letters {
    position: absolute;
    bottom: 0;
    text-align: center;
    align-items: center;
    justify-content: center;
    text-align: center;
  vertical-align: middle;
}

span {
    margin-left: 5px;
}

body {
		margin: 0;
		display: grid;
		min-height: 10vh;
		place-items: center;
		background-color: lightgray;
	}

div {
		text-align: center;
        margin-bottom: 10px;
	}

tr {
    border: solid;
    font-size: 24px;
    text-align: center;
    }

td {
    background-color: white;
    border: 2px solid;
    white-space: pre-line;
    text-align: center;
    }
</style>

<title>Wordle Wannabe</title></head>
<link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
<body>
    <h1>Clay's Wordle-like Game That Is Legally Distinct from Wordle!</h1>
	<div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "426px" height = "116px"></div>
    <h3>HINTS:</h3>
    <div>%s</div><div style = "margin-bottom: 50px;"></div>
    """ % (HINT,)

    QUERY = "SELECT attempts, won FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
    DATA = (user_ip, )
    cur.execute(QUERY, DATA)
    result = cur.fetchone()
    try:
        user_attempts = result[0] # type: ignore
        solved = result[1] # type: ignore
    except: #catches if user has not made any attempts
        user_attempts = 0
        solved = False
    if user_attempts < 6 and not solved:
        html_content +=  """    <form id="myForm" method = "POST" action = "/guess">
		<label>Guess here: <input autofocus  style="margin-bottom: 50px;" type = "text" id = "myInput" name = "guess" minlength = "5" maxlength="5" onkeypress="return isAlphabet(event)" required></label>
		<span></span><button type = "submit" id = "myBtn">Guess word!</button>        
        </form>

        """
    attempted_words: list[str] = []
    x = 1
    while x <= user_attempts:
        QUERY = f"SELECT attempt_{x} FROM wordle WHERE (ip_address = '{user_ip}' AND attempt_date = CURRENT_DATE);"
        cur.execute(QUERY)
        result = cur.fetchone()
        attempted_words.append(result[0]) # type: ignore
        x += 1    

    for word in attempted_words:
        color_1 = "gray"
        color_2 = "gray"
        color_3 = "gray"
        color_4 = "gray"
        color_5 = "gray"
        for i in range(5):
            if word[i] in TEST_WORD:
                match i:
                    case 0:
                        color_1 = "yellow"
                    case 1:
                        color_2 = "yellow"
                    case 2:
                        color_3 = "yellow"
                    case 3:
                        color_4 = "yellow"
                    case 4:
                        color_5 = "yellow"
            if word[i] == TEST_WORD[i]:
                match i:
                    case 0:
                        color_1 = "green"
                    case 1:
                        color_2 = "green"
                    case 2:
                        color_3 = "green"
                    case 3:
                        color_4 = "green"
                    case 4:
                        color_5 = "green"
        html_content += f""" <table>
                <tr>
                    <td style="background-color: {color_1}; padding: 5px;" <b> {word[0]}</td>
                    <td style="background-color: {color_2};padding: 5px;" <b> {word[1]}</td>
                    <td style="background-color: {color_3};padding: 5px;" <b> {word[2]}</td>
                    <td style="background-color: {color_4};padding: 5px;" <b> {word[3]}</td>
                    <td style="background-color: {color_5};padding: 5px;" <b> {word[4]}</td>
                </tr>
"""
        if word == TEST_WORD and user_attempts > 1:
            html_content += "</table><div>YOU GOT THE WORD!!!! A WINNER IS YOU!</div>"
        elif word == TEST_WORD and user_attempts == 1:
            html_content += "</table><div>You cheated, didn't you? I'm telling Benny.</div>"
    if user_attempts == 6 and solved == False:
        html_content += "</table><div>You ran out of attempts! Try again tomorrow!</div>"

    html_content +="""   </table>
    <div class="letters">LETTERS TRIED SO FAR
                <table class="attempted_letters">
    """ 
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    QUERY = "SELECT letters_used FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
    DATA = (user_ip, )
    cur.execute(QUERY, DATA)
    result = cur.fetchone()
    try:
        letters_used = result[0] # type: ignore
        for letter in letters_used:
            if letter not in TEST_WORD:            
                if letter in ROW_1:
                    ALPHA_COLORS_1[letter] = 'gray'
                if letter in ROW_2:
                    ALPHA_COLORS_2[letter] = 'gray'
                if letter in ROW_3:
                    ALPHA_COLORS_3[letter] = 'gray'
            if letter in TEST_WORD:            
                if letter in ROW_1:
                    ALPHA_COLORS_1[letter] = 'yellow'
                if letter in ROW_2:
                    ALPHA_COLORS_2[letter] = 'yellow'
                if letter in ROW_3:
                    ALPHA_COLORS_3[letter] = 'yellow'
    except Exception as e:
        for key in ALPHA_COLORS_1:
            ALPHA_COLORS_1[key] = "white"
        for key in ALPHA_COLORS_2:
            ALPHA_COLORS_2[key] = "white"
        for key in ALPHA_COLORS_3:
            ALPHA_COLORS_3[key] = "white"
        print("User has made no attempts yet, probably.")
    html_content += "<tr>"
    for key in ALPHA_COLORS_1:
        html_content += f'''<td style ="background-color: {ALPHA_COLORS_1[key]}; padding: 5px;"<b> {key}</td>'''
    html_content += '<td style ="background-color: white; padding: 0px;"><img src="/static/la jaiba.png" alt = "JAIBA!" width = "25px" height = "25px"> </td></tr>'

    html_content += '<tr><td style="max-width: 5px; background-color: lightgray; padding: 5px; border: 0px;"</td>'
    for key in ALPHA_COLORS_2:
        html_content += f'''<td style ="background-color: {ALPHA_COLORS_2[key]}; padding: 5px;"<b> {key}</td>'''
    html_content += "</tr>"

    html_content += '<tr><td style="background-color: lightgray; padding: 5px; border: 0px;"</td><td style="background-color: lightgray; padding: 5px; border: 0px;"</td>'
    for key in ALPHA_COLORS_3:
        html_content += f'''<td style ="background-color: {ALPHA_COLORS_3[key]}; padding: 5px;"<b> {key}</td>'''
    
    html_content += """</tr></table>
        
 <script>
        const myInput = document.getElementById('myInput');
        const myForm = document.getElementById('myForm');
        const myBtn = document.getElementById('myBtn');

        myInput.addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        myBtn.click();
    }
  });

        function isAlphabet(event) {
        var charCode = (event.which) ? event.which : event.keyCode;
        if ((charCode >= 65 && charCode <= 90) || (charCode >= 97 && charCode <= 122)) {
            return true; 
        }
        return false;
        }
               
        async function refreshPage() {
        console.log("Attempting page refresh.");
        window.location.href = window.location.href;
        window.location.href = window.location.href;
}
        myForm.addEventListener('submit', refreshPage);

</script>
                </body>
            </html>"""
    return HTMLResponse(content = html_content)

@app.post("/guess")
async def process_guess(request: Request, guess: str = Form(...)):
    user_ip = request.client.host # type: ignore
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()

    QUERY = "SELECT attempts FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
    DATA = (user_ip, )
    cur.execute(QUERY, DATA)
    result = cur.fetchone()
    try:
        attempts = result[0] # type: ignore
    except: 
        attempts = 0
    if attempts < 6:
        if guess.lower() in WORDS:
            try: 
                QUERY = "SELECT attempts, letters_used FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
                DATA = (user_ip, )
                cur.execute(QUERY, DATA)
                result = cur.fetchone()
                no_of_attempts: int = result[0] # type: ignore
                attempted_letters = result[1] # type: ignore
                attempt_number = no_of_attempts + 1
                for letter in guess.upper():
                    if letter not in attempted_letters:
                        attempted_letters += letter
                sorted_letters = sorted(attempted_letters)
                sorted_string = "".join(sorted_letters)

                QUERY = f"UPDATE wordle SET attempts = '{attempt_number}', attempt_{attempt_number} = '{guess.upper()}',  letters_used = '{sorted_string}' WHERE (ip_address = '{user_ip}' AND attempt_date = CURRENT_DATE);"
                cur.execute(QUERY)
                cur.close()
                con.commit()
                if guess.upper() == TEST_WORD:
                    con = psycopg2.connect(CONNECT_STR)
                    cur = con.cursor()
                    QUERY = "UPDATE wordle SET won = True WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
                    DATA = (user_ip, )
                    cur.execute(QUERY, DATA)
                    cur.close()
                    con.commit()                
            except:
                attempted_letters = ""
                for letter in guess:
                    if letter not in attempted_letters:
                        attempted_letters += letter               
                con = psycopg2.connect(CONNECT_STR)
                cur = con.cursor()
                QUERY = "INSERT INTO wordle (ip_address, attempt_1, letters_used) VALUES (%s, %s, %s);"
                DATA = (user_ip, guess.upper(), "".join(sorted(attempted_letters.upper())))
                cur.execute(QUERY, DATA)
                cur.close()
                con.commit()
                if guess.upper() == TEST_WORD:
                    con = psycopg2.connect(CONNECT_STR)
                    cur = con.cursor()
                    QUERY = "UPDATE wordle SET won = True WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
                    DATA = (user_ip, )
                    cur.execute(QUERY, DATA)
                    cur.close()
                    con.commit()
            return RedirectResponse(url="/", status_code=303)
        else:
            return HTMLResponse(content=f"{guess} is not an acceptable word. If you think this is a mistake, please tell Clay about it along with the word you used.<br>Go back and try another word.")

def init_db():
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor() 
    # word of day is not yet used
    cur.execute('''CREATE TABLE IF NOT EXISTS wordle 
                (id SERIAL PRIMARY KEY, 
                ip_address INET,
                attempts INT DEFAULT 1,
                attempt_1 TEXT,
                attempt_2 TEXT,
                attempt_3 TEXT,
                attempt_4 TEXT,
                attempt_5 TEXT,
                attempt_6 TEXT,
                attempt_date DATE DEFAULT CURRENT_DATE,
                letters_used TEXT,
                won BOOLEAN DEFAULT FALSE,
                word_of_day TEXT) 
                ;'''
            )
    cur.close()
    con.commit()