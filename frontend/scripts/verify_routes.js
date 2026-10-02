const http = require('http');

const routes = [
  '/',
  '/admin/dashboard',
  '/admin/ai-generator',
  '/admin/questions',
  '/admin/events',
  '/admin/students',
  '/admin/analytics',
  '/admin/leaderboards',
  '/student/dashboard',
  '/student/events',
  '/student/events/event-1',
  '/student/leaderboard',
  '/student/reports',
  '/student/archive/event-1',
  '/non-existent-route'
];

async function checkFrontend() {
  console.log('====================================================');
  console.log('       CODESPHERE FRONTEND ROUTE AUDIT             ');
  console.log('====================================================');
  
  let allPass = true;

  for (const r of routes) {
    await new Promise((resolve) => {
      http.get('http://localhost:3000' + r, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          const expectedStatus = (r === '/non-existent-route') ? (res.statusCode === 404 || res.statusCode === 200) : (res.statusCode === 200);
          const hasAntiFlash = data.includes('document.documentElement.classList');
          const hasError = data.includes('Internal Server Error') || data.includes('Application error');
          
          const pass = expectedStatus && !hasError;
          if (!pass) allPass = false;

          console.log(`Route: ${r.padEnd(28)} | HTTP ${res.statusCode} | Bytes: ${data.length.toString().padStart(6)} | AntiFlash: ${hasAntiFlash ? 'OK' : 'MISSING'} | Status: ${pass ? 'PASS' : 'FAIL'}`);
          resolve();
        });
      }).on('error', (err) => {
        console.error(`Route ${r} ERROR:`, err.message);
        allPass = false;
        resolve();
      });
    });
  }

  console.log('----------------------------------------------------');
  console.log(`FRONTEND ROUTE VERDICT: ${allPass ? 'ALL ROUTES PASS' : 'ISSUES DETECTED'}`);
}

async function checkBackendAPIs() {
  console.log('\n====================================================');
  console.log('       CODESPHERE BACKEND API AUDIT               ');
  console.log('====================================================');

  // Step 1: Login to get a valid JWT token
  let token = '';
  try {
    const loginRes = await new Promise((resolve, reject) => {
      const postData = JSON.stringify({ email: 'placement@ipu.ac.in', password: 'admin123' });
      const req = http.request({
        hostname: 'localhost',
        port: 8000,
        path: '/api/v1/auth/login',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        }
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve({ statusCode: res.statusCode, body }));
      });
      req.on('error', reject);
      req.write(postData);
      req.end();
    });

    if (loginRes.statusCode === 200) {
      const parsed = JSON.parse(loginRes.body);
      token = parsed.access_token;
      console.log(`Auth Login: HTTP 200 | Token Acquired: ${token.substring(0, 20)}... | PASS`);
    } else {
      console.log(`Auth Login: HTTP ${loginRes.statusCode} | ${loginRes.body}`);
    }
  } catch (err) {
    console.error('Auth Login Error:', err.message);
  }

  // Step 2: Get first student ID
  let firstStudentId = 1;
  try {
    const stdRes = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: 'localhost',
        port: 8000,
        path: '/api/v1/students/',
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body)));
      });
      req.on('error', reject);
      req.end();
    });
    if (Array.isArray(stdRes) && stdRes.length > 0) {
      firstStudentId = stdRes[0].id;
    }
  } catch (err) {}

  // Step 3: Create a test question to verify question creation and execution
  let testQuestionId = 1;
  try {
    const qData = JSON.stringify({
      title: "Sum of Two Numbers",
      problem_statement: "Given two space-separated integers, compute their sum.",
      input_format: "Two integers A and B separated by space.",
      output_format: "A single integer denoting the sum.",
      constraints: "1 <= A, B <= 10^9",
      examples: [{ input: "4 7", output: "11", explanation: "4 + 7 = 11" }],
      topic_tags: ["Math", "Basics"],
      difficulty_score: 2,
      expected_time_complexity: "O(1)",
      expected_space_complexity: "O(1)",
      time_limit_seconds: 2.0,
      memory_limit_mb: 256,
      status: "APPROVED",
      reference_solutions: {
        "python": "a, b = map(int, input().split())\nprint(a + b)",
        "cpp": "#include <iostream>\nusing namespace std;\nint main() { int a, b; if (cin >> a >> b) cout << a + b; return 0; }"
      },
      test_cases: [
        { input_data: "4 7", expected_output: "11", is_hidden: false, points: 10 }
      ]
    });
    const createQRes = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: 'localhost',
        port: 8000,
        path: '/api/v1/questions/',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Content-Length': Buffer.byteLength(qData)
        }
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve({ statusCode: res.statusCode, body }));
      });
      req.on('error', reject);
      req.write(qData);
      req.end();
    });
    if (createQRes.statusCode === 200 || createQRes.statusCode === 201) {
      const parsed = JSON.parse(createQRes.body);
      testQuestionId = parsed.id;
      console.log(`Question Creation: HTTP ${createQRes.statusCode} | Created ID: ${testQuestionId} | PASS`);
    } else {
      console.log(`Question Creation: HTTP ${createQRes.statusCode} | ${createQRes.body}`);
    }
  } catch (err) {
    console.error('Create Question Error:', err.message);
  }

  // Step 4: Create a test event
  let testEventId = 1;
  try {
    const eventData = JSON.stringify({
      title: "USAR Placement Assessment Round 1",
      description: "Live Technical Assessment for 3rd & 4th year candidates",
      start_time: new Date(Date.now() - 3600000).toISOString(),
      end_time: new Date(Date.now() + 7200000).toISOString(),
      duration_minutes: 120,
      departments: ["AIML", "AR", "IIOT"],
      eligible_years: [3, 4],
      is_published: true,
      question_ids: [testQuestionId]
    });
    const createEventRes = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: 'localhost',
        port: 8000,
        path: '/api/v1/events/',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Content-Length': Buffer.byteLength(eventData)
        }
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve({ statusCode: res.statusCode, body }));
      });
      req.on('error', reject);
      req.write(eventData);
      req.end();
    });
    if (createEventRes.statusCode === 200 || createEventRes.statusCode === 201) {
      const parsed = JSON.parse(createEventRes.body);
      testEventId = parsed.id;
      console.log(`Event Creation: HTTP ${createEventRes.statusCode} | Created ID: ${testEventId} | PASS`);
    }
  } catch (err) {}

  const apis = [
    { method: 'GET', path: '/health', unauthed: true },
    { method: 'GET', path: '/api/v1/questions/' },
    { method: 'GET', path: `/api/v1/questions/${testQuestionId}` },
    { method: 'GET', path: '/api/v1/events/' },
    { method: 'GET', path: `/api/v1/events/${testEventId}` },
    { method: 'GET', path: '/api/v1/leaderboards/lifetime' },
    { method: 'GET', path: '/api/v1/analytics/overview' },
    { method: 'GET', path: '/api/v1/students/' },
    { method: 'GET', path: `/api/v1/students/${firstStudentId}/history` },
    { 
      method: 'POST', 
      path: '/api/v1/execute/run', 
      body: { 
        question_id: testQuestionId, 
        code: 'a, b = map(int, input().split())\nprint(a + b)', 
        language: 'python', 
        custom_input: '10 25' 
      } 
    }
  ];

  let allPass = true;

  for (const api of apis) {
    await new Promise((resolve) => {
      const headers = {};
      if (api.body) headers['Content-Type'] = 'application/json';
      if (!api.unauthed && token) headers['Authorization'] = `Bearer ${token}`;

      const postBody = api.body ? JSON.stringify(api.body) : null;
      if (postBody) headers['Content-Length'] = Buffer.byteLength(postBody);

      const options = {
        hostname: 'localhost',
        port: 8000,
        path: api.path,
        method: api.method,
        headers
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          const pass = res.statusCode >= 200 && res.statusCode < 300;
          if (!pass) allPass = false;
          let summary = '';
          try {
            const parsed = JSON.parse(data);
            if (Array.isArray(parsed)) summary = `Array (${parsed.length} items)`;
            else if (typeof parsed === 'object') summary = Object.keys(parsed).join(', ').substring(0, 45);
          } catch {
            summary = data.substring(0, 45);
          }
          console.log(`API: [${api.method}] ${api.path.padEnd(38)} | HTTP ${res.statusCode} | Data: ${summary} | ${pass ? 'PASS' : 'FAIL'}`);
          resolve();
        });
      });

      req.on('error', (err) => {
        console.error(`API [${api.method}] ${api.path} ERROR:`, err.message);
        allPass = false;
        resolve();
      });

      if (postBody) {
        req.write(postBody);
      }
      req.end();
    });
  }

  console.log('----------------------------------------------------');
  console.log(`BACKEND API VERDICT: ${allPass ? 'ALL APIS PASS' : 'ISSUES DETECTED'}`);
}

async function run() {
  await checkFrontend();
  await checkBackendAPIs();
}

run();
