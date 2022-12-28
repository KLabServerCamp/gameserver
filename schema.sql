DROP TABLE IF EXISTS `room_member`;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL,
  `max_user_count` int NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `room_member` (
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` tinyint NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);

INSERT INTO `user` (name, token, leader_card_id) VALUES ('user1', '2759ebe2-4f27-4fd4-94ae-d2f666902918', 1);
INSERT INTO `user` (name, token, leader_card_id) VALUES ('user2', '4245ebe2-4f27-4fd4-94ae-d2f666902919', 2);

INSERT INTO `room` (live_id, joined_user_count, max_user_count) VALUES (0, 1, 4);
INSERT INTO `room_member` (user_id, room_id, select_difficulty, is_host) VALUES (1, 1, 0, 1)




