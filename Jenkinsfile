pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Pre-flight Checks') {
            steps {
                sh '''
                        command -v docker >/dev/null || { echo "Docker not found"; exit 1; }
                        command -v git >/dev/null || { echo "Git not found"; exit 1; }
                        [ -f requirements.txt ] || { echo "requirements.txt not found"; exit 1; }
                        [ -f docker-compose.yml ] || { echo "docker-compose.yml not found"; exit 1; }
                        echo "✓ All prerequisites satisfied"
                    '''
                }
            }
        }

        stage('Build') {
            }
        }

        stage('Build') {
            steps {
        }"
                    '''
            }
        }

        stage('Unit Tests') {
            steps {
                '''
                }
            }'''
            }
        }

        stage('Integration Tests') {
            steps {
                '''
                }
                post {
                    '''
            }
            post {
                failure {
                    echo 'Integration tests failed - stopping build'
                }
            }
        }

        stage('Code Coverage') {
            steps {
            }
            }
            post {
                always {
                    publishHTML([
                        reportDir: 'coverage_report',
                        reportFiles: 'index.html',
                        reportName: 'Code Coverage Report'
                    ])
                }'''
            }
            post {
                always {
                    publishHTML([
                        reportDir: 'coverage_report',
                        reportFiles: 'index.html',
                        reportName: 'Code Coverage Report'
                    ])
                }
            }
        }

        stage('Start Services') {
            when {
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS' }
            }
            steps {
                            break
                            fi
                            retry_count=$((retry_count + 1))
                            sleep 1
                        done
                        
                        [ $retry_count -lt $max_retries ] || { echo "API health check failed"; exit 1; }
                        
            }
        }
    }

    post {
        always {
            script {
                echo '==== Pipeline Summary ===='
                sh '''
                    echo "Build Status: ${BUILD_STATUS:-SUCCESS}"
                    docker compose ps || true
                '''
            }
        }
        failure {'''
            }
        }
    }

    post {
        always {
            sh 'docker compose ps || true'
        }
        failure {
            sh 'docker compose logs | tail -50 || true'
        }
        success {
            echo 'Build successful. Services ready at http://localhost:8080'