pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.11'
    }

    stages {

        stage('Checkout') {
            steps {
                git url: 'https://github.com/TON-REPO.git', branch: 'main'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '''
                python -m pip install --upgrade pip
                pip install -r requirements.txt
                pip install pytest flake8 black
                '''
            }
        }

        stage('Lint') {
            steps {
                bat 'flake8 .'
            }
        }

        stage('Tests') {
            steps {
                bat 'pytest'
            }
        }

        stage('Validate Code') {
            steps {
                bat '''
                python -m py_compile main.py
                python -m py_compile services/Auth.py
                python -m py_compile services/Fetch.py
                python -m py_compile services/Normalisation.py
                '''
            }
        }

        stage('Run Dashboard') {
            steps {
                bat 'streamlit run main.py'
            }
        }
    }
}
