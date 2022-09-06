DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `name` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `score` int,
  `judge` varchar(255),
  PRIMARY KEY (`room_id`, `user_id`)
);