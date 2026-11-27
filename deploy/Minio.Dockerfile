FROM golang:1.26-alpine AS build
# MinIO Community Edition ships as source. Pin the upstream revision.
RUN CGO_ENABLED=0 go install github.com/minio/minio@7aac2a2c5b7c882e68c1ce017d8256be2feea27f

FROM alpine:3.23
RUN adduser -D -u 10001 minio && mkdir /data && chown minio:minio /data
COPY --from=build /go/bin/minio /usr/local/bin/minio
USER minio
ENTRYPOINT ["minio"]
