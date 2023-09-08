use webapp;

-- DROP TABLE IF EXISTS `user`;
CREATE TABLE IF NOT EXISTS `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE IF NOT EXISTS `room` (
    `id` bigint NOT NULL AUTO_INCREMENT,
    `live_id` int NOT NULL,
    `owner_id` bigint,
    `status` int DEFAULT 1,
    `players` int DEFAULT 0,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`owner_id`) REFERENCES `user`(`id`)
);

CREATE TABLE IF NOT EXISTS `room_member` (
    `room_id` bigint NOT NULL,
    `user_id` bigint NOT NULL,
    `score` int,
    `judge_count_list` json,
    `difficulty` int,
    PRIMARY KEY (`room_id`, `user_id`),
    FOREIGN KEY (`room_id`) REFERENCES `room`(`id`),
    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`)
);
