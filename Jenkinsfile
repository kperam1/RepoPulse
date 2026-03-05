pipeline {
    agent any

    environment {
        // InfluxDB + Grafana env vars for docker-compose
        INFLUX_INIT_USERNAME = 'repopulse'
        INFLUX_INIT_PASSWORD = 'repopulse_pass12345'
        INFLUX_ORG           = 'RepoPulseOrg'
        INFLUX_BUCKET        = 'repopulse_metrics'
        INFLUX_INIT_TOKEN    = 'devtoken12345'
        INFLUX_RETENTION_DAYS = '90'
        INFLUX_URL           = 'http://influxdb:8086'
        INFLUX_TOKEN         = 'devtoken12345'
        GF_ADMIN_USER        = 'admin'
        GF_ADMIN_PASSWORD    = 'admin'
    }

    stages {

        // ── Stage 1: Checkout ────────────────────────────────────────────
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

        // ── Stage 2: Build Docker Image ──────────────────────────────────
        stage('Build Docker Image') {
            steps {
                sh 'docker compose build --no-cache'
            }
        }

        // ── Stage 3: Unit Tests (inside container) ───────────────────────
        stage('Unit Tests') {
            steps {
                sh '''
                    mkdir -p reports
                    docker compose run --rm \
                        -e PYTHONPATH=/app \
                        api python -m pytest tests/ -v \
                            --junitxml=/app/reports/unit-tests.xml \
                            --cov=src --cov-branch \
                            --cov-report=term-missing \
                            --cov-report=html:/app/reports/coverage-html \
                            --cov-report=xml:/app/reports/coverage.xml \
                            --cov-fail-under=80
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/unit-tests.xml'
                }
            }
        }

        // ── Stage 4: Coverage Report ─────────────────────────────────────
        stage('Coverage Report') {
            steps {
                echo 'Publishing HTML coverage report …'
                publishHTML(target: [
                    reportDir:   'reports/coverage-html',
                    reportFiles: 'index.html',
                    reportName:  'Coverage Report',
                    keepAll:     true,
                    alwaysLinkToLastBuild: true,
                    allowMissing: true
                ])
            }
        }

        // ── Stage 5: Service / API-Driven Test ──────────────────────────
        stage('Service Test') {
            steps {
                sh '''
                    echo "Starting containers …"
                    docker compose up -d

                    echo "Waiting for API to become healthy …"
                    MAX_RETRIES=30
                    RETRY=0
                    until docker compose exec -T api curl -sf http://localhost:8080/health > /dev/null 2>&1; do
                        RETRY=$((RETRY + 1))
                        if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
                            echo "API did not start within $MAX_RETRIES attempts"
                            docker compose logs api
                            exit 1
                        fi
                        echo "  retry $RETRY/$MAX_RETRIES …"
                        sleep 3
                    done
                    echo "API is healthy ✓"

                    echo "Running service-level tests …"

                    # Test 1: Health endpoint returns 200
                    HTTP_CODE=$(docker compose exec -T api curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
                    if [ "$HTTP_CODE" != "200" ]; then
                        echo "FAIL: /health returned $HTTP_CODE"
                        exit 1
                    fi
                    echo "  ✓ GET /health → 200"

                    # Test 2: API docs returns 200
                    HTTP_CODE=$(docker compose exec -T api curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/docs)
                    if [ "$HTTP_CODE" != "200" ]; then
                        echo "FAIL: /docs returned $HTTP_CODE"
                        exit 1
                    fi
                    echo "  ✓ GET /docs → 200"

                    # Test 3: POST /analyze with a small repo
                    RESPONSE=$(docker compose exec -T api curl -s -w "\n%{http_code}" \
                        -X POST http://localhost:8080/analyze \
                        -H "Content-Type: application/json" \
                        -d '{"repo_url": "https://github.com/pallets/markupsafe"}')
                    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
                    BODY=$(echo "$RESPONSE" | sed '$d')
                    if [ "$HTTP_CODE" != "200" ]; then
                        echo "FAIL: POST /analyze returned $HTTP_CODE"
                        echo "$BODY"
                        exit 1
                    fi
                    echo "  ✓ POST /analyze → 200"

                    # Test 4: Verify the response contains expected fields
                    if ! echo "$BODY" | grep -q '"total_loc"'; then
                        echo "FAIL: /analyze response missing total_loc field"
                        echo "$BODY"
                        exit 1
                    fi
                    echo "  ✓ /analyze response contains total_loc"

                    echo ""
                    echo "All service tests passed ✓"
                '''
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
            // Tear down containers regardless of build result
            sh 'docker compose down --volumes --remove-orphans || true'
        }
        success {
            echo '✅ Pipeline completed successfully — all tests passed!'
        }
        failure {
            echo '❌ Pipeline FAILED — check the stage that turned red above.'
        }
    }
}
            sh 'docker compose ps || true'
        }
        failure {
            sh 'docker compose logs | tail -50 || true'
        }
        success {
            echo 'Build successful. Services ready at http://localhost:8080'
