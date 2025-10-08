#wordle-like
#technically works!
#port 42069

import psycopg2
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import toml
from random import randint

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static") #logo and favicon go here

CONFIG = toml.load("./config.toml") # load variables from toml file
CONNECT_STR = f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']} host = {CONFIG['credentials']['host']}'

TEST_WORD = "LEARN" # 5 letter word, all caps. This is the word the users are trying to guess.
HINT = "You do this to acquire new skills or knowledge!" # The hint you can show to users to guide them towards the correct answer.

WORDS: list[str] = []

QWERTY = 'QWERTYUIOPASDFGHJKLZXCVBNM'
# dictionary is structured like {A : ["white", False]}. The False means the letter isn't in the right spot. Will be used
# later to turn the letter "green" in the letters shown on the bottom of the page.

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

@app.get("/", response_class=HTMLResponse) # page with actual game
async def get_form(request: Request) -> HTMLResponse:
    ALPHA_COLORS = {letter: ['white', False] for letter in QWERTY} # moved down here because otherwise the user's browser might cache the wrong colors
    user_ip = request.client.host # type: ignore
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor()
    QUERY = "SELECT has_read_rules FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
    DATA = (user_ip, )
    cur.execute(QUERY, DATA)
    result = cur.fetchone()
    try:
        rulesRead = result[0] # type: ignore
    except:
        rulesRead = False
    if rulesRead == True:
        display_rules = 'none'
    else:
        display_rules = 'flex'

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

.popup {
            display: %s;
            opacity: 1; 
            position: fixed; 
            z-index: 1; 
            width: 100rem; 
            height: 100rem; 
            overflow: auto; 
            background-color: lightgray; 
            justify-content: center; 
            align-items: center; 
        }

.popup-content {
            background-color: #fefefe;
            margin: auto;
            padding: 20px;
            border: 1px solid #888;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            width: 80rem; 
            text-align: center;
            max-width: 500px; 
            border-radius: 5px;
            position: relative;
        }

.close-button {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }

        .close-button:hover,
        .close-button:focus {
            color: black;
            text-decoration: none;
            cursor: pointer;
        }
</style>

<title>Wordle Wannabe</title></head>
<link rel="icon" type = "image/x-icon" href="/static/favicon.ico">
<body>
    <h1>Clay's Wordle-like Game That Is Legally Distinct from Wordle!</h1>
	<div><img src="/static/dhr-logo.png" alt = "DHR Logo" width = "426px" height = "116px"></div>
    
          <button onclick="openPopup()">Rules / How to Play</button>

    <div id="myPopup" class="popup">
        <div class="popup-content">
            <span class="close-button" onclick="closePopup()">&times;</span>
            <h2>Rules and How to Play</h2>
            <p>This is my knockoff of the popular game "Wordle."</p>
            <p>Basically, you get 6 chances to guess a 5 letter word. You're given a hint to try to guide you in the right direction.</p>
            <p>Type a 5 letter word into the box, press Enter (or click "Guess word!), and you'll see how close your guess was.</p>
            <p>Whenever you make a guess, letters that are in the word will be colored <span style = "color: yellow; background-color: black;"><b>YELLOW</b></span>.</p>
            <p>Letters that are in the word AND in the correct spot in the world will be colored<span style = "color: green;"><b>GREEN</b></span>.</p>
            <p>You can keep track of what letters you tried with the onscreen keyboard on the bottom of the page. Attempted letters are gray, letters that are in the word are
            yellow, and letters which you've found the correct location for are green.</p>
             <button style= "box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);" onclick="closeRules()">Start playing!</button>
        </div>
    </div>

    <h3>HINTS:</h3>
    <div>%s</div><div style = "margin-bottom: 50px;"></div>
    """ % (display_rules, HINT)

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
        html_content +=  """<form id="myForm" method = "POST" action = "/guess">
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
                ALPHA_COLORS[word[i]][1] = True # This is used to signal that the letter will be colored green in the onscreen keyboard
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
                    <td style="background-color: {color_2}; padding: 5px;" <b> {word[1]}</td>
                    <td style="background-color: {color_3}; padding: 5px;" <b> {word[2]}</td>
                    <td style="background-color: {color_4}; padding: 5px;" <b> {word[3]}</td>
                    <td style="background-color: {color_5}; padding: 5px;" <b> {word[4]}</td>
                </tr>
"""
        if word == TEST_WORD and user_attempts > 1:
            html_content += "</table><div>YOU GOT THE WORD!!!! A WINNER IS YOU!</div>"
        elif word == TEST_WORD and user_attempts == 1:
            html_content += f"</table><div>{CONFIG['first_try_messages'][str(randint(1, 6))]}</div>" # picks random message to show to user if they get it in one try. found in TOML
    if user_attempts == 6 and not solved:
        html_content += "</table><div>You ran out of attempts! Try again tomorrow!</div>"

    html_content += """</table>
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
            if letter in TEST_WORD:
                ALPHA_COLORS[letter][0] = "yellow"
                if ALPHA_COLORS[letter][1] == True:
                    ALPHA_COLORS[letter][0] = "green"
            else:    
                ALPHA_COLORS[letter][0] = "gray"
    except Exception as e:
        for letter in ALPHA_COLORS:
            ALPHA_COLORS[letter][0] = "white"
        print("User has made no attempts yet, probably.\n", e)
    html_content += "<tr>"
    
    # Onscreen keyboard that shows users which letters have been attempted, which are in the word, and which have their correct spots figured out.
    # Uses logic above to determine what color the letter is going to be. By default, they are white. 
    # Probably a better way to do it. I'll figure out a better way soon, I promise!
    for letter in QWERTY[0: 10]:
        html_content += f'''<td style ="background-color: {ALPHA_COLORS[letter][0]}; padding: 5px;"<b> {letter}</td>'''
    html_content += '<td style ="background-color: white; padding: 0px;"><img src="/static/la jaiba.png" alt = "JAIBA!" width = "25px" height = "25px"> </td></tr>'
    
    html_content += '<tr><td style="max-width: 5px; background-color: lightgray; padding: 5px; border: 0px;"</td>'

    for letter in QWERTY[10: 19]: 
        html_content += f'''<td style ="background-color: {ALPHA_COLORS[letter][0]}; padding: 5px;"<b> {letter}</td>'''
    html_content += "</tr>"
    
    html_content += '<tr><td style="background-color: lightgray; padding: 5px; border: 0px;"</td><td style="background-color: lightgray; padding: 5px; border: 0px;"</td>'

    for letter in QWERTY[19: 27]: 
        html_content += f'''<td style ="background-color: {ALPHA_COLORS[letter][0]}; padding: 5px;"<b> {letter}</td>'''
    
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

         function openPopup() {
            document.getElementById('myPopup').style.display = 'flex';
        }

        function closePopup() {
            document.getElementById('myPopup').style.display = 'none';
        }

        function closeRules() {
            document.getElementById('myPopup').style.display = 'none';
        }

        document.getElementById('openPopupBtn').addEventListener('click', openPopup);

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
        if guess.lower() not in WORDS:
            return HTMLResponse(content=f"""
                                {guess} is not an acceptable word. If you think this is a mistake, please tell Clay about it along with the word you used.
                                <div></div>Go back and try another word.""")
        else:
            try: 
                QUERY = "SELECT attempts, letters_used FROM wordle WHERE (ip_address = %s AND attempt_date = CURRENT_DATE);"
                DATA = (user_ip, )
                cur.execute(QUERY, DATA)
                result = cur.fetchone()
                attempt_number: int = result[0] # type: ignore
                attempted_letters = result[1] # type: ignore
                attempt_number += 1
                for letter in guess.upper():
                    if letter not in attempted_letters:
                        attempted_letters += letter
                sorted_letters = sorted(attempted_letters)
                sorted_string = "".join(sorted_letters)

                QUERY = f"""
                UPDATE wordle SET attempts = '{attempt_number}', 
                attempt_{attempt_number} = '{guess.upper()}',  
                letters_used = '{sorted_string}' 
                WHERE 
                (ip_address = '{user_ip}' 
                AND 
                attempt_date = CURRENT_DATE);"""
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
            

def init_db():
    con = psycopg2.connect(CONNECT_STR)
    cur = con.cursor() 
    # word of day is not yet used
    cur.execute("""CREATE TABLE IF NOT EXISTS wordle 
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
                ;"""
            )
    cur.close()
    con.commit()