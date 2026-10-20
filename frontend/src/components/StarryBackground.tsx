import React, { useEffect, useRef } from 'react';
import './StarryBackground.css';

export const StarryBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 设置画布大小
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // 粒子类 - 持续飘动的发光粒子
    class Particle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      opacity: number;
      color: string;
      glowSize: number;
      pulseSpeed: number;
      pulsePhase: number;

      constructor() {
        this.x = Math.random() * canvas!.width;
        this.y = Math.random() * canvas!.height;
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;
        this.size = Math.random() * 2 + 1;
        this.opacity = Math.random() * 0.5 + 0.5;

        // 多种颜色：蓝色、紫色、青色
        const colors = [
          'rgba(139, 92, 246, ',  // 紫色
          'rgba(59, 130, 246, ',  // 蓝色
          'rgba(34, 211, 238, ',  // 青色
          'rgba(167, 139, 250, ', // 淡紫
          'rgba(255, 255, 255, '  // 白色
        ];
        this.color = colors[Math.floor(Math.random() * colors.length)];

        this.glowSize = Math.random() * 20 + 10;
        this.pulseSpeed = Math.random() * 0.02 + 0.01;
        this.pulsePhase = Math.random() * Math.PI * 2;
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;

        // 边界检测 - 循环出现
        if (this.x < 0) this.x = canvas!.width;
        if (this.x > canvas!.width) this.x = 0;
        if (this.y < 0) this.y = canvas!.height;
        if (this.y > canvas!.height) this.y = 0;

        // 脉动效果
        this.pulsePhase += this.pulseSpeed;
        this.opacity = (Math.sin(this.pulsePhase) + 1) / 2 * 0.4 + 0.6;
      }

      draw() {
        if (!ctx) return;

        // 外层光晕
        const gradient = ctx.createRadialGradient(
          this.x, this.y, 0,
          this.x, this.y, this.glowSize
        );
        gradient.addColorStop(0, this.color + this.opacity + ')');
        gradient.addColorStop(0.5, this.color + (this.opacity * 0.3) + ')');
        gradient.addColorStop(1, this.color + '0)');

        ctx.beginPath();
        ctx.arc(this.x, this.y, this.glowSize, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        // 核心亮点
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color + this.opacity + ')';
        ctx.fill();
      }
    }

    // 连接线类 - 粒子之间的连接
    class Connection {
      static draw(p1: Particle, p2: Particle) {
        if (!ctx) return;

        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < 150) {
          const opacity = (1 - distance / 150) * 0.3;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(139, 92, 246, ${opacity})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    // 流星类 - 快速划过的流星
    class ShootingStar {
      x: number;
      y: number;
      length: number;
      speed: number;
      angle: number;
      opacity: number;
      life: number;
      color: string;

      constructor() {
        this.x = Math.random() * canvas!.width;
        this.y = Math.random() * canvas!.height * 0.5;
        this.length = Math.random() * 120 + 80;
        this.speed = Math.random() * 10 + 8;
        this.angle = Math.PI / 4 + (Math.random() - 0.5) * 0.3;
        this.opacity = 1;
        this.life = 1;

        const colors = [
          'rgba(139, 92, 246, ',  // 紫色
          'rgba(59, 130, 246, ',  // 蓝色
          'rgba(255, 255, 255, '  // 白色
        ];
        this.color = colors[Math.floor(Math.random() * colors.length)];
      }

      draw() {
        if (!ctx) return;

        this.x += Math.cos(this.angle) * this.speed;
        this.y += Math.sin(this.angle) * this.speed;
        this.life -= 0.008;
        this.opacity = this.life;

        const gradient = ctx.createLinearGradient(
          this.x,
          this.y,
          this.x - Math.cos(this.angle) * this.length,
          this.y - Math.sin(this.angle) * this.length
        );
        gradient.addColorStop(0, this.color + this.opacity + ')');
        gradient.addColorStop(0.5, this.color + (this.opacity * 0.5) + ')');
        gradient.addColorStop(1, this.color + '0)');

        ctx.beginPath();
        ctx.moveTo(this.x, this.y);
        ctx.lineTo(
          this.x - Math.cos(this.angle) * this.length,
          this.y - Math.sin(this.angle) * this.length
        );
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      isDead() {
        return this.life <= 0 || this.x > canvas!.width || this.y > canvas!.height;
      }
    }

    // 创建粒子 - 更多粒子
    const particles: Particle[] = [];
    for (let i = 0; i < 100; i++) {
      particles.push(new Particle());
    }

    // 流星数组
    let shootingStars: ShootingStar[] = [];
    let lastShootingStarTime = 0;

    // 动画循环
    const animate = (timestamp: number) => {
      if (!ctx) return;

      // 不完全清除，产生轨迹效果
      ctx.fillStyle = 'rgba(2, 6, 23, 0.1)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // 更新和绘制粒子
      particles.forEach(particle => {
        particle.update();
        particle.draw();
      });

      // 绘制连接线
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          Connection.draw(particles[i], particles[j]);
        }
      }

      // 频繁生成流星（每 0.5-1.5 秒）
      if (timestamp - lastShootingStarTime > Math.random() * 1000 + 500) {
        shootingStars.push(new ShootingStar());
        lastShootingStarTime = timestamp;
      }

      // 绘制流星
      shootingStars = shootingStars.filter(star => {
        star.draw();
        return !star.isDead();
      });

      requestAnimationFrame(animate);
    };

    const animationId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationId);
    };
  }, []);

  return (
    <div className="starry-background">
      <canvas ref={canvasRef} className="starry-canvas" />
    </div>
  );
};
