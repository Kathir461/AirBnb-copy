CREATE DATABASE IF NOT EXISTS stayclub
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS users (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(80) NOT NULL,
 email VARCHAR(254) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS stays (
 id INT UNSIGNED PRIMARY KEY,
 title VARCHAR(150) NOT NULL,
 location VARCHAR(100) NOT NULL,
 category VARCHAR(50) NOT NULL,
 description VARCHAR(200) NOT NULL,
 price INT UNSIGNED NOT NULL,
 rating DECIMAL(3,2) NOT NULL,
 image VARCHAR(100) NOT NULL,
 badge VARCHAR(30) NOT NULL DEFAULT 'Guest favourite'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS wishlists (
 user_id BIGINT UNSIGNED NOT NULL,
 stay_id INT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id, stay_id),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY(stay_id) REFERENCES stays(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS bookings (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT UNSIGNED NOT NULL,
 stay_id INT UNSIGNED NOT NULL,
 check_in DATE NOT NULL,
 check_out DATE NOT NULL,
 adults INT UNSIGNED NOT NULL,
 children INT UNSIGNED NOT NULL DEFAULT 0,
 nightly_price INT UNSIGNED NOT NULL,
 total_price BIGINT UNSIGNED NOT NULL,
 request_token CHAR(32) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY booking_request(user_id, request_token),
 INDEX stay_dates(stay_id, check_in, check_out),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY(stay_id) REFERENCES stays(id),
 CHECK (check_out > check_in),
 CHECK (adults >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS login_attempts (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 email VARCHAR(254) NOT NULL,
 attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX email_time(email, attempted_at), INDEX attempt_time(attempted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO stays (id,title,location,category,description,price,rating,image,badge) VALUES
(1,'The Palm House','Lonavala, India','Amazing pools','Entire villa · 6 guests · 3 bedrooms',8500,4.98,'stay-1.jpg','Guest favourite'),
(2,'A little slice of paradise','Ubud, Indonesia','Amazing pools','Entire villa · 4 guests · 2 bedrooms',6200,4.95,'stay-2.jpg','Guest favourite'),
(3,'Slow mornings in the mountains','Manali, India','Cabins','Entire cabin · 2 guests · 1 bedroom',4800,4.99,'stay-3.jpg','Guest favourite'),
(4,'The Moonlit Retreat','Galle, Sri Lanka','Design','Entire home · 4 guests · 2 bedrooms',7900,4.92,'stay-4.jpg','Guest favourite'),
(5,'Sunshine & open spaces','Alibaug, India','Design','Entire villa · 6 guests · 3 bedrooms',11200,4.96,'stay-5.jpg','Guest favourite'),
(6,'A cabin away from it all','Coorg, India','Countryside','Entire cabin · 2 guests · 1 bedroom',3900,4.89,'stay-6.jpg','Guest favourite');
