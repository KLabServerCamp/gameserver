use webapp;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

INSERT INTO `user` (id, name, token, leader_card_id) VALUES (51, "Taro", "7gOuy9Rr", "1001");
INSERT INTO `user` (id, name, token, leader_card_id) VALUES (52, "Jiro", "Yy4ZERso", "1002");
INSERT INTO `user` (id, name, token, leader_card_id) VALUES (53, "Saburo", "nBdQ0V1k", "1003");
INSERT INTO `user` (id, name, token, leader_card_id) VALUES (54, "Yonro", "urF4rWPw", "1002");
INSERT INTO `user` (id, name, token, leader_card_id) VALUES (55, "Goro", "0TVbIz00", "1002");

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` int NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner_id` bigint NOT NULL,
  `max_user_count` int DEFAULT 4,
  PRIMARY KEY (`id`)
);

INSERT INTO `room` (id, live_id, owner_id) VALUES (61, 1, 51);
INSERT INTO `room` (id, live_id, owner_id) VALUES (62, 2, 52);
INSERT INTO `room` (id, live_id, owner_id) VALUES (63, 3, 53);


DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `latest_score` int DEFAULT NULL,
  `selected_difficulty` int NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);


INSERT INTO `room_member` (room_id, user_id, selected_difficulty) VALUES (61, 51, 1);
INSERT INTO `room_member` (room_id, user_id, selected_difficulty) VALUES (62, 52, 1);
INSERT INTO `room_member` (room_id, user_id, selected_difficulty) VALUES (61, 54, 1);
INSERT INTO `room_member` (room_id, user_id, selected_difficulty) VALUES (61, 55, 1);