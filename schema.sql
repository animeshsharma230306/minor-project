CREATE TABLE IF NOT EXISTS Users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  email VARCHAR(150),
  daily_hours FLOAT NOT NULL DEFAULT 3,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS Exams (
  exam_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(150) DEFAULT 'Final exam',
  exam_date DATE NOT NULL,
  FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Subjects (
  subject_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  name VARCHAR(120) NOT NULL,
  priority TINYINT NOT NULL DEFAULT 2,
  difficulty TINYINT NOT NULL DEFAULT 2,
  FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Topics (
  topic_id INT AUTO_INCREMENT PRIMARY KEY,
  subject_id INT NOT NULL,
  unit VARCHAR(120),
  title VARCHAR(255) NOT NULL,
  prerequisite VARCHAR(255),
  complexity TINYINT NOT NULL DEFAULT 2,
  FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Study_Schedule (
  schedule_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  subject_id INT NOT NULL,
  topic_id INT NULL,
  scheduled_date DATE NOT NULL,
  title VARCHAR(300) NOT NULL,
  session_type ENUM('study','revise','practice') NOT NULL,
  allocated_mins INT NOT NULL,
  status ENUM('pending','done','partial','missed') NOT NULL DEFAULT 'pending',
  moved BOOLEAN NOT NULL DEFAULT FALSE,
  rescheduled BOOLEAN NOT NULL DEFAULT FALSE,
  FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subjects(subject_id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES Topics(topic_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS Progress_Logs (
  log_id INT AUTO_INCREMENT PRIMARY KEY,
  schedule_id INT NOT NULL,
  status ENUM('pending','done','partial','missed') NOT NULL,
  logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (schedule_id) REFERENCES Study_Schedule(schedule_id) ON DELETE CASCADE
);
