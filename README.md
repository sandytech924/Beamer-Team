# Beamer Team – shared link manager

Team leader (admin) links add panni team members ku share pannalam. Members employee ID + password vechu login panni, avangaluku share panna links-ah mattum paakalam.

## Features
- Login with **Employee ID + Password** (no self-signup)
- **Team Leader (admin):** unlimited team members - add, edit name / employee ID, reset password, deactivate / activate, remove. Can create links, see **all** links (with who added them) and edit / delete any link.
- **Team Member:** creates multiple links, edits / deletes **own** links, sees links from admin and every other member
- **All links are public to the team** - no private or member-specific links. A new link shows up instantly in All Links for everyone.
- Filter by member (Everyone / Me / a person), **My Links** page, search, category filter, favourites, change own password
- **Copy button**, **dark / light mode**, **favicon**, responsive, hashed passwords, CSRF protection, login attempt limit

## Run
```bash
python -m venv venv
venv\Scripts\activate        # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Default logins (first run only) – change them!
| Role | Employee ID | Password |
|------|-------------|----------|
| Team Leader | EMP001 | admin123 |
| Sample members | EMP101 – EMP104 | member123 |

Login panna aprm **Change password** use pannunga. Admin-ku Team page-la members' name / ID / password edit-um panna mudiyum (Reset).

## PostgreSQL (optional)
Default SQLite. PostgreSQL use panna `DATABASE_URL` set pannunga, apram `pip install -r requirements.txt`:
```bash
# Windows (cmd)
set DATABASE_URL=postgresql://user:password@localhost:5432/beamer
# Mac/Linux
export DATABASE_URL=postgresql://user:password@localhost:5432/beamer
python app.py
```

## Notes
- Database: `instance/beamer_team.db` (auto-created). Reset pannanum na intha file-ah delete pannitu run pannunga.
- Production-la run panna `SECRET_KEY` environment variable set pannunga.
- Old Beamer `links.db` data intha version-ku varadhu (new database use pannudhu).
