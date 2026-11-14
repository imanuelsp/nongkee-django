# nongkee

A student platform for discovering and joining study sessions at Fasilkom UI.

## Run locally

Use Python 3.12 or newer. From the repository root in PowerShell, create the virtual environment once if `.venv` is missing:

```powershell
python -m venv .venv
```

Use the existing virtual environment to install dependencies, apply migrations, and start Django:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open [nongkee](http://127.0.0.1:8000/) and create an account. Start a meet by choosing a date, time, and location. Hosts can allow direct joins or review join requests in the meet details. My Meets shows hosted meets, confirmed attendance, and pending requests.

Kelas Kosong uses the weekly timetable supplied with the HTML export and accounts for other nongkee meets. Update `meets/data/timetable.json` when the timetable changes. All times use Jakarta time.
