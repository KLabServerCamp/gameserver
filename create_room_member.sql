DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `name` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `user_id` (`user_id`)
);