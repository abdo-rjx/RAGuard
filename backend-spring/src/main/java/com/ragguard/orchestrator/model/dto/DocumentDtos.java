package com.ragguard.orchestrator.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

public class DocumentDtos {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UploadResponse {
        private Long documentId;
        private String status;
        private String message;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DocumentResponse {
        private Long id;
        private String title;
        private String fileType;
        private Long fileSize;
        private String department;
        private String classificationLevel;
        private String status;
        private Integer chunkCount;
        private java.time.Instant createdAt;
        private java.time.Instant updatedAt;
        private java.time.Instant indexedAt;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DocumentListResponse {
        private List<DocumentResponse> documents;
        private long totalElements;
        private int totalPages;
        private int currentPage;
        private int pageSize;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UpdateDocumentRequest {
        @Size(max = 500)
        private String title;

        @Size(max = 100)
        private String department;

        @Size(max = 50)
        private String classificationLevel;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReindexRequest {
        private List<Long> documentIds;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SearchRequest {
        @NotBlank
        @Size(max = 500)
        private String query;

        private Integer limit = 10;

        private Double threshold = 0.7;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SearchResult {
        private Long documentId;
        private String title;
        private String snippet;
        private double score;
    }
}