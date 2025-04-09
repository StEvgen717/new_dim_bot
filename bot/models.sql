CREATE DATABASE IF NOT EXISTS telegram_db;
USE telegram_db;

CREATE TABLE IF NOT EXISTS cities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS streets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    city_id INT,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    surname VARCHAR(100),
    name VARCHAR(100),
    patronymic VARCHAR(100),
    contract_number VARCHAR(50),
    units INT,
    volume VARCHAR(50),
    payment_status ENUM('СПЛАЧЕНО', 'НЕ СПЛАЧЕНО'),
    street_id INT,
    FOREIGN KEY (street_id) REFERENCES streets(id) ON DELETE CASCADE
);