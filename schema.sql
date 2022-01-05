DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `join_user`;
CREATE TABLE `join_user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `difficulty` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `room_id` int DEFAULT NULL,
  `is_host` boolean DEFAULT FALSE,
  PRIMARY KEY (`id`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `joined_user_account` int DEFAULT 0,
  `max_user_count` int DEFAULT 1,
  `owner_token` varchar(255) DEFAULT NULL,
  `is_dissolution` boolean DEFAULT FALSE,
  PRIMARY KEY (`id`)
);

INSERT INTO user(name,token,leader_card_id) VALUES ('ほのか','asdfghjkl','12345');
INSERT INTO user(name,token,leader_card_id) VALUES ('ことり','zxcv','88998');
INSERT INTO user(name,token,leader_card_id) VALUES ('うみ','qwert','173248');

INSERT INTO room(live_id,joined_user_account,max_user_count,owner_token) VALUES (1, 1, 4, 'asdfghjkl');
INSERT INTO room(live_id,joined_user_account,max_user_count,owner_token) VALUES (2, 1, 4, 'zxcv');

INSERT INTO join_user(user_id,room_id) VALUES (0, 0);
INSERT INTO join_user(user_id,room_id) VALUES (1, 1);

SELECT * FROM user WHERE name='うみ';
SELECT * FROM user WHERE name LIKE 'ほ%';

SELECT * FROM room;
