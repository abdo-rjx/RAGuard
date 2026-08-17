package com.ragguard.orchestrator.model;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.Instant;

@Entity
@Table(name = "documents")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 500)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String content;

    @Column(name = "file_path", length = 1000)
    private String filePath;

    @Column(name = "file_type", length = 50)
    private String fileType;

    @Column(name = "file_size")
    private Long fileSize;

    @Column(name = "owner_id", nullable = false)
    private Long ownerId;

    @Column(name = "department", length = 100)
    private String department;

    @Column(name = "classification_level", length = 50)
    private String classificationLevel; // PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED

    @Column(name = "status", length = 50)
    @Builder.Default
    private String status = "PENDING"; // PENDING, PROCESSING, INDEXED, FAILED

    @Column(name = "chunk_count")
    @Builder.Default
    private Integer chunkCount = 0;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private Instant updatedAt;

    @Column(name = "indexed_at")
    private Instant indexedAt;
}