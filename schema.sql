DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `join`;
CREATE TABLE `join` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `difficulty` varchar(255) DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `room_id` int DEFAULT NULL,
  `is_me` boolean DEFAULT FALSE,
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

INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'ほのか','asdfghjkl','12345');
INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'ことり','zxcv','88998');
INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'うみ','qwert','173248');

INSERT INTO room(live_id,joined_user_account,max_user_count,owner_token) VALUES (1, 2, 4, 'asdfghjkl');
INSERT INTO room(live_id,joined_user_account,max_user_count,owner_token) VALUES (2, 3, 4, 'zxcv');
INSERT INTO room(live_id,joined_user_account,max_user_count,owner_token) VALUES (3, 1, 4, 'qwert');

SELECT * FROM user WHERE name='うみ';
SELECT * FROM user WHERE name LIKE 'ほ%';

SELECT * FROM room;
