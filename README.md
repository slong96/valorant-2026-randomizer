# Valorant 2026 Randomizer

A Django web app for randomizing Valorant Agents for 1-5 players.

## Getting Started to Run on Local Host

### Prerequisites

- Python 3.x
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd valorant-2026-randomizer
   ```

2. **Create virtual enviornment**

   Make sure [Python](https://www.python.org/downloads/) is installed, then set up a virtual environment:

   **macOS/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   **Windows:**
   ```bash
   python -m venv venv
   . venv\Scripts\activate
   ```

3. **Remove `psycopg2` from requirements**

   Open `requirements.txt` and remove the following line before installing dependencies, as it may cause installation errors:

   ```
   psycopg2==2.9.11
   ```

4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configure settings**

   In `valorant_stack_project/settings.py`, ensure:

   ```python
   DEBUG = True
   ```

6. **Create a `.env` file**

   In the root of the project directory, create a `.env` file:

   ```bash
   export SECRET_KEY='your_secret_key_here'
   export ALLOWED_HOSTS='localhost'
   ```

   > Generate a secret key at [https://djecrety.ir/](https://djecrety.ir/)

7. **Run migrations and start the server**

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

   The app will be available at `http://127.0.0.1:8000/`
